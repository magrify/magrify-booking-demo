import { httpAction, internalQuery } from './_generated/server';
import { internal } from './_generated/api';
import { v } from 'convex/values';

type KnowledgeInput = {
  property_slug?: string;
  question?: string;
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function authorized(request: Request): boolean {
  const expected = process.env.MAGRIFY_LIVEKIT_TOKEN?.trim();
  const supplied = request.headers.get('authorization')?.replace(/^Bearer\s+/iu, '').trim();
  return Boolean(expected && supplied && supplied === expected);
}

function terms(value: string): string[] {
  return value
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .map((term) => term.trim())
    .filter((term) => term.length >= 3)
    .slice(0, 24);
}

/**
 * Structured, property-scoped retrieval. This intentionally uses Convex rows
 * and keyword matching rather than embeddings, so each tenant can inspect and
 * update the knowledge used by its phone concierge.
 */
export const search = internalQuery({
  args: { propertySlug: v.string(), question: v.string() },
  handler: async (ctx, args) => {
    const property = await ctx.db
      .query('properties')
      .withIndex('by_slug', (q) => q.eq('slug', args.propertySlug))
      .first();
    if (!property || !property.active) return null;

    const unitTypes = await ctx.db
      .query('unitTypes')
      .withIndex('by_property', (q) => q.eq('propertyId', property._id))
      .collect();
    const rows = await ctx.db
      .query('propertyKnowledge')
      .withIndex('by_property_active', (q) => q.eq('propertyId', property._id).eq('active', true))
      .collect();
    const queryTerms = terms(args.question);
    const ranked = rows
      .map((row) => {
        const haystack = `${row.title} ${row.content} ${row.tags.join(' ')}`.toLowerCase();
        const score = queryTerms.reduce((sum, term) => sum + (haystack.includes(term) ? 1 : 0), 0);
        return { row, score };
      })
      .filter(({ score }) => queryTerms.length === 0 || score > 0)
      .sort((a, b) => b.score - a.score || b.row.updatedAt - a.row.updatedAt)
      .slice(0, 8)
      .map(({ row }) => ({
        kind: row.kind,
        title: row.title,
        content: row.content,
        tags: row.tags,
      }));

    return {
      property: {
        name: property.name,
        slug: property.slug,
        address: property.address,
        phone: property.phone,
        timezone: property.timezone,
        check_in_time: property.checkInTime,
        check_out_time: property.checkOutTime,
      },
      unit_types: unitTypes
        .filter((unitType) => !unitType.comingSoon)
        .sort((a, b) => a.sortOrder - b.sortOrder)
        .map((unitType) => ({
          name: unitType.name,
          slug: unitType.slug,
          description: unitType.description,
          max_occupancy: unitType.maxOccupancy,
          amenities: unitType.amenities,
        })),
      knowledge: ranked,
    };
  },
});

/** Token-authenticated vectorless knowledge bridge for LiveKit Agents. */
export const handle = httpAction(async (ctx, request) => {
  if (!authorized(request)) return json({ error: 'unauthorized' }, 401);
  try {
    const body = await request.json() as KnowledgeInput;
    const propertySlug = body.property_slug?.trim() ?? '';
    const question = body.question?.trim() ?? '';
    if (!propertySlug || propertySlug.length > 120 || question.length > 500) {
      return json({ error: 'invalid_request' }, 400);
    }
    const result = await ctx.runQuery(internal.voiceKnowledge.search, {
      propertySlug,
      question,
    });
    if (!result) return json({ error: 'property_not_found' }, 404);
    return json(result);
  } catch (error) {
    console.error('Voice knowledge request failed', error);
    return json({ error: 'voice_knowledge_failed' }, 500);
  }
});
