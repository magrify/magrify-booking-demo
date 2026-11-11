import { ConvexError } from 'convex/values';
import { httpAction } from './_generated/server';
import { api, internal } from './_generated/api';
import { daysBetween } from '../shared/pricing';

type VoiceBookingInput = {
  property_slug?: string;
  unit_type_slug?: string;
  check_in?: string;
  check_out?: string;
  adults?: number;
  children?: number;
  email?: string;
  phone?: string;
  name?: string;
  hold_requested?: boolean;
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

/**
 * Narrow, token-authenticated voice surface for the LiveKit concierge.
 * It delegates to the same availability query and createHold mutation used by
 * the guest UI, so the phone path keeps the platform's pricing and conflict
 * protections without exposing the full staff API.
 */
export const handle = httpAction(async (ctx, request) => {
  if (!authorized(request)) return json({ error: 'unauthorized' }, 401);

  try {
    const body = await request.json() as VoiceBookingInput;
    const propertySlug = body.property_slug?.trim() ?? '';
    const unitTypeSlug = body.unit_type_slug?.trim() ?? '';
    const checkIn = body.check_in?.trim() ?? '';
    const checkOut = body.check_out?.trim() ?? '';
    const adults = Number(body.adults ?? 0);
    const children = Number(body.children ?? 0);
    const email = body.email?.trim().toLowerCase() ?? '';
    if (!propertySlug || !unitTypeSlug || !checkIn || !checkOut || !email || !email.includes('@')) {
      return json({ error: 'invalid_request', message: 'Property, dates, occupancy, and email are required.' }, 400);
    }
    const nights = daysBetween(checkIn, checkOut);
    if (!Number.isInteger(nights) || nights < 1 || !Number.isInteger(adults) || adults < 1 || !Number.isInteger(children) || children < 0) {
      return json({ error: 'invalid_request', message: 'Dates and occupancy are invalid.' }, 400);
    }

    const property = await ctx.runQuery(internal.apiV1.propertyBySlug, { slug: propertySlug });
    if (!property) return json({ status: 'unavailable', reason: 'property_not_found' }, 404);
    const unitTypes = await ctx.runQuery(internal.apiV1.unitTypesForProperty, { slug: propertySlug });
    const unitType = unitTypes?.find((candidate) => candidate.slug === unitTypeSlug);
    if (!unitType) return json({ status: 'unavailable', reason: 'unit_type_not_found' }, 404);

    const availability = await ctx.runQuery(api.availability.forUnitType, {
      unitTypeId: unitType.unitTypeId,
      startDate: checkIn,
      days: nights,
    });
    const endDate = checkOut;
    const availableUnits = availability.units.filter((unit) =>
      (!unit.bookableFrom || checkIn >= unit.bookableFrom) &&
      !unit.blockedDates.some((date) => date >= checkIn && date < endDate),
    );
    if (availableUnits.length === 0) {
      return json({ status: 'unavailable', property: property.slug, unit_type: unitType.slug, check_in: checkIn, check_out: checkOut });
    }

    const plans = await ctx.runQuery(internal.apiV1.ratePlansForUnitType, {
      propertySlug,
      unitTypeSlug,
    });
    const ratePlan = plans?.ratePlans[0];
    if (!ratePlan) return json({ status: 'awaiting_configuration', reason: 'rate_plan_not_configured' });

    if (!body.hold_requested) {
      return json({
        status: 'available',
        property: property.slug,
        unit_type: unitType.slug,
        unit: availableUnits[0],
        rate_plan: ratePlan,
        check_in: checkIn,
        check_out: checkOut,
        nights,
      });
    }

    const hold = await ctx.runMutation(api.bookings.createHold, {
      unitId: availableUnits[0].unitId,
      ratePlanId: ratePlan.ratePlanId,
      checkIn,
      checkOut,
      adults,
      children,
      guest: {
        name: body.name?.trim() || 'Phone guest',
        email,
        phone: body.phone?.trim() || '',
        marketingOptIn: false,
      },
      addOns: [],
    });
    return json({
      status: 'hold_created',
      property: property.slug,
      unit_type: unitType.slug,
      ...hold,
      payment_next_step: 'secure_payment_link',
    });
  } catch (error) {
    if (error instanceof ConvexError) {
      return json({ error: error.data }, 409);
    }
    console.error('Voice booking request failed', error);
    return json({ error: 'voice_booking_failed' }, 500);
  }
});
