import { ConvexError, v } from 'convex/values';
import { internalMutation, mutation, query } from './_generated/server';
import { internal } from './_generated/api';
import { requirePropertyCapability } from './staff';

const channel = v.union(v.literal('website'), v.literal('chat'), v.literal('phone'));
const status = v.union(
  v.literal('new'),
  v.literal('qualified'),
  v.literal('booking_started'),
  v.literal('converted'),
  v.literal('closed'),
);

function clean(value: string, max: number): string {
  return value.replace(/[\u0000-\u001F\u007F]/gu, '').trim().slice(0, max);
}

function normalizedEmail(value: string): string {
  const email = value.trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email)) throw new ConvexError({ code: 'INVALID_EMAIL', message: 'Enter a valid email address.' });
  return email;
}

export const create = mutation({
  args: {
    propertySlug: v.string(),
    channel,
    name: v.string(),
    email: v.string(),
    phone: v.string(),
    message: v.string(),
    checkIn: v.optional(v.string()),
    checkOut: v.optional(v.string()),
    adults: v.optional(v.number()),
    children: v.optional(v.number()),
    marketingOptIn: v.boolean(),
    source: v.string(),
  },
  handler: async (ctx, args) => {
    const property = await ctx.db
      .query('properties')
      .withIndex('by_slug', (q) => q.eq('slug', args.propertySlug.trim()))
      .first();
    if (!property?.active) throw new ConvexError({ code: 'PROPERTY_NOT_FOUND', message: 'This property is not accepting inquiries.' });
    const email = normalizedEmail(args.email);
    const name = clean(args.name, 120);
    const message = clean(args.message, 2_000);
    if (!name || !message) throw new ConvexError({ code: 'INQUIRY_REQUIRED', message: 'Name and a short message are required.' });
    const now = Date.now();
    const phone = clean(args.phone, 40);
    const guest = await ctx.db
      .query('guests')
      .withIndex('by_email', (q) => q.eq('propertyId', property._id).eq('normalizedEmail', email))
      .first();
    const guestId = guest?._id ?? await ctx.db.insert('guests', {
      propertyId: property._id,
      name,
      email: args.email.trim(),
      phone,
      normalizedEmail: email,
      normalizedPhone: phone.replace(/\D/gu, ''),
      marketingOptIn: args.marketingOptIn,
      notes: [],
    });
    if (guest && (args.marketingOptIn || phone)) {
      await ctx.db.patch(guest._id, {
        name,
        phone: phone || guest.phone,
        marketingOptIn: guest.marketingOptIn || args.marketingOptIn,
      });
    }
    const inquiryId = await ctx.db.insert('inquiries', {
      propertyId: property._id,
      guestId,
      channel: args.channel,
      status: 'new',
      name,
      email: args.email.trim(),
      phone,
      normalizedEmail: email,
      message,
      checkIn: args.checkIn,
      checkOut: args.checkOut,
      adults: args.adults,
      children: args.children,
      marketingOptIn: args.marketingOptIn,
      source: clean(args.source || 'website', 80),
      followUpStatus: 'not_due',
      followUpAttempts: 0,
      deskcommStatus: 'pending',
      deskcommAttempts: 0,
      createdAt: now,
      updatedAt: now,
    });
    await ctx.scheduler.runAfter(0, internal.inquiryAdapters.syncInquiry, { inquiryId });
    await ctx.scheduler.runAfter(0, internal.agentOrchestrator.startInquiryRun, { inquiryId });
    return { inquiryId, propertyName: property.name };
  },
});

export const listForStaff = query({
  args: { propertyId: v.id('properties'), status: v.optional(status) },
  handler: async (ctx, args) => {
    await requirePropertyCapability(ctx, args.propertyId, 'guest.read');
    const rows = args.status
      ? await ctx.db.query('inquiries').withIndex('by_property_status', (q) => q.eq('propertyId', args.propertyId).eq('status', args.status!)).order('desc').take(100)
      : await ctx.db.query('inquiries').withIndex('by_property_status', (q) => q.eq('propertyId', args.propertyId)).order('desc').take(100);
    return rows.map((row) => ({
      inquiryId: row._id,
      name: row.name,
      email: row.email,
      phone: row.phone,
      channel: row.channel,
      status: row.status,
      message: row.message,
      checkIn: row.checkIn,
      checkOut: row.checkOut,
      source: row.source,
      deskcommStatus: row.deskcommStatus,
      followUpStatus: row.followUpStatus,
      agentStatus: row.agentStatus ?? 'not_configured',
      agentRunId: row.agentRunId,
      createdAt: row.createdAt,
    }));
  },
});

export const qualify = mutation({
  args: {
    propertyId: v.id('properties'),
    inquiryId: v.id('inquiries'),
    status,
    qualificationNote: v.string(),
  },
  handler: async (ctx, args) => {
    await requirePropertyCapability(ctx, args.propertyId, 'quote.write');
    const inquiry = await ctx.db.get(args.inquiryId);
    if (!inquiry || inquiry.propertyId !== args.propertyId) throw new ConvexError('INQUIRY_NOT_FOUND');
    await ctx.db.patch(args.inquiryId, {
      status: args.status,
      qualificationNote: clean(args.qualificationNote, 1_000),
      updatedAt: Date.now(),
    });
    await ctx.scheduler.runAfter(0, internal.inquiryAdapters.syncInquiry, { inquiryId: args.inquiryId });
    return { updated: true };
  },
});

export const setAgentApproval = mutation({
  args: { propertyId: v.id('properties'), inquiryId: v.id('inquiries'), approved: v.boolean() },
  handler: async (ctx, args) => {
    await requirePropertyCapability(ctx, args.propertyId, 'quote.write');
    const inquiry = await ctx.db.get(args.inquiryId);
    if (!inquiry || inquiry.propertyId !== args.propertyId) throw new ConvexError('INQUIRY_NOT_FOUND');
    if (!inquiry.agentRunId || inquiry.agentStatus !== 'awaiting_approval') throw new ConvexError('AGENT_APPROVAL_NOT_PENDING');
    await ctx.db.patch(args.inquiryId, { agentStatus: args.approved ? 'approved' : 'rejected', updatedAt: Date.now() });
    await ctx.scheduler.runAfter(0, internal.agentOrchestrator.approveInquiryRun, { inquiryId: args.inquiryId, approved: args.approved });
    return { updated: true };
  },
});

export const markBookingStarted = mutation({
  args: { inquiryId: v.id('inquiries') },
  handler: async (ctx, args) => {
    const inquiry = await ctx.db.get(args.inquiryId);
    if (!inquiry) throw new ConvexError('INQUIRY_NOT_FOUND');
    const dueAt = Date.now() + 30 * 60_000;
    await ctx.db.patch(args.inquiryId, {
      status: 'booking_started',
      followUpStatus: 'scheduled',
      followUpDueAt: dueAt,
      updatedAt: Date.now(),
    });
    await ctx.scheduler.runAfter(30 * 60_000, internal.inquiryAdapters.sendRecoveryFollowUp, { inquiryId: args.inquiryId });
    await ctx.scheduler.runAfter(0, internal.inquiryAdapters.syncInquiry, { inquiryId: args.inquiryId });
    return { dueAt };
  },
});

export const attachBooking = internalMutation({
  args: { propertyId: v.id('properties'), bookingId: v.id('bookings'), normalizedEmail: v.string() },
  handler: async (ctx, args) => {
    const rows = await ctx.db.query('inquiries').withIndex('by_property_email', (q) => q.eq('propertyId', args.propertyId).eq('normalizedEmail', args.normalizedEmail)).collect();
    const open = rows.filter((row) => row.status !== 'converted' && row.status !== 'closed').sort((a, b) => b.createdAt - a.createdAt)[0];
    if (!open) return;
    await ctx.db.patch(open._id, {
      status: 'booking_started',
      bookingId: args.bookingId,
      followUpStatus: 'scheduled',
      followUpDueAt: Date.now() + 30 * 60_000,
      updatedAt: Date.now(),
    });
    await ctx.scheduler.runAfter(30 * 60_000, internal.inquiryAdapters.sendRecoveryFollowUp, { inquiryId: open._id });
    await ctx.scheduler.runAfter(0, internal.inquiryAdapters.syncInquiry, { inquiryId: open._id });
  },
});

export const markConverted = internalMutation({
  args: { bookingId: v.id('bookings') },
  handler: async (ctx, args) => {
    const booking = await ctx.db.get(args.bookingId);
    if (!booking || !booking.guestId) return;
    const guest = await ctx.db.get(booking.guestId);
    if (!guest) return;
    const rows = await ctx.db
      .query('inquiries')
      .withIndex('by_property_email', (q) => q.eq('propertyId', booking.propertyId).eq('normalizedEmail', guest.normalizedEmail))
      .collect();
    const open = rows.find((row) => row.bookingId === booking._id) ?? rows.filter((row) => row.status === 'booking_started').sort((a, b) => b.createdAt - a.createdAt)[0];
    if (!open) return;
    await ctx.db.patch(open._id, { status: 'converted', bookingId: booking._id, followUpStatus: 'cancelled', updatedAt: Date.now() });
    await ctx.scheduler.runAfter(0, internal.inquiryAdapters.syncInquiry, { inquiryId: open._id });
  },
});
