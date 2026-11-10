import { internalMutation } from './_generated/server';
import type { MutationCtx } from './_generated/server';

/** Example inventory only. No Woodland operational data is represented here. */
export const seed = internalMutation({
  args: {},
  handler: async (ctx) => seedWoodland(ctx),
});

export async function seedWoodland(ctx: MutationCtx) {
    const existing = await ctx.db.query('properties').withIndex('by_slug', (q) => q.eq('slug', 'woodland-rv-demo')).first();
    if (existing) return { seeded: false, propertyId: existing._id };
    const propertyId = await ctx.db.insert('properties', {
      name: 'Woodland RV Resort — Magrify Demo', slug: 'woodland-rv-demo',
      timezone: 'America/New_York', currency: 'USD', taxRateBps: 0, taxLabel: 'Demo tax',
      email: 'support@magrify.com', phone: '(469) 269-0355',
      address: '421 Mac Thompson Road, Cochran, GA 31014',
      checkInTime: '15:00', checkOutTime: '11:00', active: true,
    });
    for (const [amp, order] of [[30, 1], [50, 2]] as const) {
      const unitTypeId = await ctx.db.insert('unitTypes', {
        propertyId, name: `${amp}-amp full-hookup RV site (sample)`, slug: `rv-${amp}-amp`,
        kind: 'site', bookingMode: 'nightly',
        description: 'Example site inventory for the Magrify mockup. Availability shown here is simulated and does not reflect Woodland RV Resort.',
        photoUrls: [], maxOccupancy: 6, amenities: [`${amp}-amp power`, 'Water', 'Sewer', 'Wi-Fi'],
        comingSoon: false, sortOrder: order,
      });
      for (let i = 1; i <= 3; i++) {
        await ctx.db.insert('units', {
          propertyId, unitTypeId, name: `Demo ${amp}-${i}`, slug: `demo-${amp}-${i}`,
          status: 'active', icalExportToken: crypto.randomUUID(), icalImports: [], sortOrder: i,
        });
      }
      await ctx.db.insert('ratePlans', {
        propertyId, unitTypeId, name: 'Published rates for illustration', active: true,
        currency: 'USD', baseNightlyCents: 4000, weeklyRateCents: 25000,
        seasons: [], minStayNights: 1, maxStayNights: 30, minLeadTimeHours: 0,
        maxAdvanceDays: 365, prepBufferNights: 0,
        depositPolicy: { type: 'full', value: 0 },
        cancellationPolicy: [{ daysBefore: 0, refundPercent: 100 }],
      });
    }
    return { seeded: true, propertyId };
}
