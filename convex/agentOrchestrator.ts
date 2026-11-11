import { v } from 'convex/values';
import { internalAction, internalMutation } from './_generated/server';
import { internal } from './_generated/api';

const runStatus = v.union(
  v.literal('queued'),
  v.literal('running'),
  v.literal('awaiting_approval'),
  v.literal('approved'),
  v.literal('rejected'),
  v.literal('completed'),
  v.literal('failed'),
);

export const setInquiryAgentStatus = internalMutation({
  args: {
    inquiryId: v.id('inquiries'),
    agentRunId: v.optional(v.string()),
    agentStatus: runStatus,
  },
  handler: async (ctx, args) => {
    const inquiry = await ctx.db.get(args.inquiryId);
    if (!inquiry) return;
    await ctx.db.patch(args.inquiryId, {
      agentRunId: args.agentRunId,
      agentStatus: args.agentStatus,
      updatedAt: Date.now(),
    });
  },
});

export const startInquiryRun = internalAction({
  args: { inquiryId: v.id('inquiries') },
  handler: async (ctx, args) => {
    const endpoint = process.env.AGENT_ORCHESTRATOR_URL?.trim();
    if (!endpoint) return;
    const context = await ctx.runQuery(internal.inquiryAdapters.getInquiry, { inquiryId: args.inquiryId });
    if (!context) return;
    await ctx.runMutation(internal.agentOrchestrator.setInquiryAgentStatus, {
      inquiryId: args.inquiryId,
      agentStatus: 'running',
    });
    try {
      const inquiry = context.inquiry;
      const property = context.property;
      const response = await fetch(`${endpoint.replace(/\/$/u, '')}/v1/runs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(process.env.AGENT_ORCHESTRATOR_TOKEN ? { Authorization: `Bearer ${process.env.AGENT_ORCHESTRATOR_TOKEN}` } : {}),
        },
        body: JSON.stringify({
          product: 'magrify',
          workflow: 'booking_concierge',
          tenant_id: property?.slug ?? String(inquiry.propertyId),
          input: {
            inquiry_id: inquiry._id,
            channel: inquiry.channel,
            email: inquiry.email,
            check_in: inquiry.checkIn,
            check_out: inquiry.checkOut,
            adults: inquiry.adults,
            children: inquiry.children,
            message: inquiry.message,
          },
          require_approval: true,
        }),
      });
      if (!response.ok) throw new Error(`Agent orchestrator HTTP ${response.status}`);
      const result = await response.json() as { run_id?: string; status?: string };
      await ctx.runMutation(internal.agentOrchestrator.setInquiryAgentStatus, {
        inquiryId: args.inquiryId,
        agentRunId: result.run_id,
        agentStatus: result.status === 'ready' ? 'completed' : 'awaiting_approval',
      });
    } catch (error) {
      await ctx.runMutation(internal.agentOrchestrator.setInquiryAgentStatus, {
        inquiryId: args.inquiryId,
        agentStatus: 'failed',
      });
      console.error('Agent orchestrator inquiry run failed', error);
    }
  },
});

export const approveInquiryRun = internalAction({
  args: { inquiryId: v.id('inquiries'), approved: v.boolean() },
  handler: async (ctx, args) => {
    const endpoint = process.env.AGENT_ORCHESTRATOR_URL?.trim();
    const context = await ctx.runQuery(internal.inquiryAdapters.getInquiry, { inquiryId: args.inquiryId });
    if (!endpoint || !context?.inquiry.agentRunId) return;
    try {
      const response = await fetch(`${endpoint.replace(/\/$/u, '')}/v1/runs/${encodeURIComponent(context.inquiry.agentRunId)}/approval`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(process.env.AGENT_ORCHESTRATOR_TOKEN ? { Authorization: `Bearer ${process.env.AGENT_ORCHESTRATOR_TOKEN}` } : {}),
        },
        body: JSON.stringify({ approved: args.approved, actor: 'magrify.staff' }),
      });
      if (!response.ok) throw new Error(`Agent approval HTTP ${response.status}`);
      await ctx.runMutation(internal.agentOrchestrator.setInquiryAgentStatus, {
        inquiryId: args.inquiryId,
        agentRunId: context.inquiry.agentRunId,
        agentStatus: args.approved ? 'approved' : 'rejected',
      });
    } catch (error) {
      await ctx.runMutation(internal.agentOrchestrator.setInquiryAgentStatus, {
        inquiryId: args.inquiryId,
        agentRunId: context.inquiry.agentRunId,
        agentStatus: 'failed',
      });
      console.error('Agent approval failed', error);
    }
  },
});
