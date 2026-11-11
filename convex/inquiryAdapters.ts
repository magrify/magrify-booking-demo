import { v } from 'convex/values';
import { internalAction, internalMutation, internalQuery } from './_generated/server';
import { internal } from './_generated/api';
import type { Id } from './_generated/dataModel';

type InquiryPayload = {
  inquiryId: Id<'inquiries'>;
  propertyId: Id<'properties'>;
  propertySlug: string;
  channel: 'website' | 'chat' | 'phone';
  status: string;
  source: string;
  hasDates: boolean;
  hasMessage: boolean;
};

// Adapter contract: DeskcommCRM (or another CRM later) receives a normalized
// inquiry payload, while the booking domain remains independent of its API.
// The adapter is disabled unless a tenant explicitly supplies a webhook URL.
export async function syncDeskcomm(payload: InquiryPayload): Promise<{ configured: boolean; ok: boolean; detail?: string }> {
  const endpoint = process.env.DESKCOMM_CRM_WEBHOOK_URL?.trim();
  if (!endpoint) return { configured: false, ok: true, detail: 'DESKCOMM_CRM_WEBHOOK_URL not configured' };
  const token = process.env.DESKCOMM_CRM_WEBHOOK_TOKEN?.trim();
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      event: 'inquiry.created',
      tenant: payload.propertySlug,
      inquiry: payload,
    }),
  });
  if (!response.ok) throw new Error(`CRM adapter HTTP ${response.status}`);
  return { configured: true, ok: true };
}

// PostHog adapter. Never send names, emails, phone numbers, or message text.
export async function capturePostHog(event: string, payload: Record<string, string | number | boolean>): Promise<boolean> {
  const apiKey = process.env.POSTHOG_API_KEY?.trim();
  if (!apiKey) return false;
  const host = (process.env.POSTHOG_HOST?.trim() || 'https://us.i.posthog.com').replace(/\/$/u, '');
  const response = await fetch(`${host}/capture/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: apiKey,
      event,
      distinct_id: String(payload.inquiry_id ?? payload.property_slug ?? 'anonymous'),
      properties: payload,
    }),
  });
  return response.ok;
}

export const getInquiry = internalQuery({
  args: { inquiryId: v.id('inquiries') },
  handler: async (ctx, args) => {
    const inquiry = await ctx.db.get(args.inquiryId);
    if (!inquiry) return null;
    const property = await ctx.db.get(inquiry.propertyId);
    return { inquiry, property };
  },
});

export const getBookingContext = internalQuery({
  args: { bookingId: v.id('bookings') },
  handler: async (ctx, args) => {
    const booking = await ctx.db.get(args.bookingId);
    if (!booking) return null;
    const property = await ctx.db.get(booking.propertyId);
    return { booking, property };
  },
});

export const updateDeskcommStatus = internalMutation({
  args: {
    inquiryId: v.id('inquiries'),
    status: v.union(v.literal('synced'), v.literal('not_configured'), v.literal('failed')),
    attempts: v.number(),
    error: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const inquiry = await ctx.db.get(args.inquiryId);
    if (!inquiry) return;
    await ctx.db.patch(args.inquiryId, {
      deskcommStatus: args.status,
      deskcommAttempts: args.attempts,
      deskcommError: args.error,
      updatedAt: Date.now(),
    });
  },
});

export const updateFollowUpStatus = internalMutation({
  args: {
    inquiryId: v.id('inquiries'),
    status: v.union(v.literal('sent'), v.literal('cancelled'), v.literal('failed')),
    attempts: v.number(),
    error: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const inquiry = await ctx.db.get(args.inquiryId);
    if (!inquiry) return;
    await ctx.db.patch(args.inquiryId, {
      followUpStatus: args.status,
      followUpAttempts: args.attempts,
      followUpError: args.error,
      updatedAt: Date.now(),
    });
  },
});

export const syncInquiry = internalAction({
  args: { inquiryId: v.id('inquiries'), attempt: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const attempt = args.attempt ?? 0;
    const context = await ctx.runQuery(internal.inquiryAdapters.getInquiry, { inquiryId: args.inquiryId });
    if (!context) return;
    const { inquiry, property } = context;
    try {
      const result = await syncDeskcomm({
        inquiryId: inquiry._id,
        propertyId: inquiry.propertyId,
        propertySlug: property?.slug ?? 'unknown',
        channel: inquiry.channel,
        status: inquiry.status,
        source: inquiry.source,
        hasDates: Boolean(inquiry.checkIn && inquiry.checkOut),
        hasMessage: inquiry.message.length > 0,
      });
      await ctx.runMutation(internal.inquiryAdapters.updateDeskcommStatus, {
        inquiryId: inquiry._id,
        status: result.configured ? 'synced' : 'not_configured',
        attempts: attempt + 1,
      });
      await capturePostHog('inquiry_submitted', {
        inquiry_id: inquiry._id,
        property_slug: property?.slug ?? 'unknown',
        channel: inquiry.channel,
        source: inquiry.source,
        has_dates: Boolean(inquiry.checkIn && inquiry.checkOut),
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'CRM adapter failed';
      await ctx.runMutation(internal.inquiryAdapters.updateDeskcommStatus, {
        inquiryId: inquiry._id,
        status: 'failed',
        attempts: attempt + 1,
        error: detail,
      });
      if (attempt < 2) {
        await ctx.scheduler.runAfter((attempt + 1) * 60_000, internal.inquiryAdapters.syncInquiry, {
          inquiryId: inquiry._id,
          attempt: attempt + 1,
        });
      }
    }
  },
});

export const sendRecoveryFollowUp = internalAction({
  args: { inquiryId: v.id('inquiries'), attempt: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const attempt = args.attempt ?? 0;
    const context = await ctx.runQuery(internal.inquiryAdapters.getInquiry, { inquiryId: args.inquiryId });
    if (!context) return;
    const { inquiry, property } = context;
    if (inquiry.status !== 'booking_started' || inquiry.followUpStatus !== 'scheduled') return;
    const apiKey = process.env.RESEND_API_KEY?.trim();
    const from = process.env.EMAIL_FROM?.trim();
    const siteUrl = (process.env.SITE_URL?.trim() || '').replace(/\/$/u, '');
    if (!apiKey || !from || !siteUrl) {
      await ctx.runMutation(internal.inquiryAdapters.updateFollowUpStatus, {
        inquiryId: inquiry._id,
        status: 'failed',
        attempts: attempt + 1,
        error: 'Recovery follow-up requires RESEND_API_KEY, EMAIL_FROM, and SITE_URL',
      });
      return;
    }
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from,
        to: [inquiry.email],
        subject: `Still looking for a stay at ${property?.name ?? 'your selected property'}?`,
        text: `You started a booking inquiry but did not finish. Continue here: ${siteUrl}/p/${property?.slug ?? ''}`,
      }),
    });
    if (response.ok) {
      await ctx.runMutation(internal.inquiryAdapters.updateFollowUpStatus, {
        inquiryId: inquiry._id,
        status: 'sent',
        attempts: attempt + 1,
      });
      await capturePostHog('booking_recovery_sent', {
        inquiry_id: inquiry._id,
        property_slug: property?.slug ?? 'unknown',
      });
      return;
    }
    const detail = `Recovery email HTTP ${response.status}`;
    if (attempt < 2) {
      await ctx.scheduler.runAfter((attempt + 1) * 60_000, internal.inquiryAdapters.sendRecoveryFollowUp, {
        inquiryId: inquiry._id,
        attempt: attempt + 1,
      });
    } else {
      await ctx.runMutation(internal.inquiryAdapters.updateFollowUpStatus, {
        inquiryId: inquiry._id,
        status: 'failed',
        attempts: attempt + 1,
        error: detail,
      });
    }
  },
});

export const trackBookingCompleted = internalAction({
  args: { bookingId: v.id('bookings') },
  handler: async (ctx, args) => {
    const context = await ctx.runQuery(internal.inquiryAdapters.getBookingContext, { bookingId: args.bookingId });
    if (!context) return;
    await capturePostHog('booking_completed', {
      booking_id: context.booking._id,
      property_slug: context.property?.slug ?? 'unknown',
      source: context.booking.source,
      nights: context.booking.nights,
      total_cents: context.booking.priceBreakdown?.totalCents ?? 0,
    });
  },
});
