import { convexTest } from 'convex-test';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { api, internal } from './_generated/api';
import schema from './schema';

const modules = import.meta.glob('./**/!(*.*.*)*.*s');

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('inquiry funnel', () => {
  it('stores a tenant-scoped inquiry and attaches the next booking', async () => {
    const t = convexTest(schema, modules);
    const propertyId = await t.run(async (ctx) => await ctx.db.insert('properties', {
      name: 'Pinewood Flats', slug: 'pinewood-flats', timezone: 'America/Edmonton', currency: 'CAD', taxRateBps: 500,
      taxLabel: 'GST', email: 'stays@example.test', phone: '555-0100', address: '1 Main St', checkInTime: '16:00', checkOutTime: '11:00', active: true,
    }));
    const created = await t.mutation(api.inquiries.create, {
      propertySlug: 'pinewood-flats', channel: 'website', name: 'Jamie Guest', email: 'jamie@example.com', phone: '555-0199',
      message: 'Do you have a pull-through site next month?', checkIn: '2026-12-10', checkOut: '2026-12-13', adults: 2, children: 0,
      marketingOptIn: true, source: 'organic',
    });
    expect(created.propertyName).toBe('Pinewood Flats');
    const inquiry = await t.run(async (ctx) => await ctx.db.get(created.inquiryId));
    expect(inquiry).toMatchObject({ propertyId, status: 'new', deskcommStatus: 'pending', followUpStatus: 'not_due' });

    const bookingId = await t.run(async (ctx) => {
      const unitTypeId = await ctx.db.insert('unitTypes', {
        propertyId, name: 'Site', slug: 'site', kind: 'site', bookingMode: 'nightly', description: '', photoUrls: [], maxOccupancy: 4,
        amenities: [], comingSoon: false, sortOrder: 1,
      });
      const unitId = await ctx.db.insert('units', {
        propertyId, unitTypeId, name: 'Site 1', slug: 'site-1', status: 'active', icalExportToken: 'test', icalImports: [], sortOrder: 1,
      });
      return await ctx.db.insert('bookings', {
      propertyId, unitId, unitTypeId, guestId: inquiry?.guestId,
      checkIn: '2026-12-10', checkOut: '2026-12-13', nights: 3, adults: 2, children: 0, status: 'hold', source: 'online',
      confirmationCode: 'OS-INQUIRY1', holdExpiresAt: Date.now() + 600_000, statusHistory: [{ status: 'hold', ts: Date.now() }], notes: [], createdAt: Date.now(), updatedAt: Date.now(),
      });
    });
    await t.mutation(internal.inquiries.attachBooking, { propertyId, bookingId, normalizedEmail: 'jamie@example.com' });
    const started = await t.run(async (ctx) => await ctx.db.get(created.inquiryId));
    expect(started).toMatchObject({ status: 'booking_started', bookingId, followUpStatus: 'scheduled' });
    await t.mutation(internal.inquiries.markConverted, { bookingId });
    const converted = await t.run(async (ctx) => await ctx.db.get(created.inquiryId));
    expect(converted).toMatchObject({ status: 'converted', bookingId, followUpStatus: 'cancelled' });
  });
});
