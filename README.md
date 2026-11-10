# Magrify Booking Platform

Magrify builds the booking and property operations platform for independent short term rental owners, campgrounds, cabins, glamping operators, and small hospitality teams. It covers direct reservations, availability, rates, guest records, staff operations, payments, refunds, email, calendar feeds, and channel synchronization in one deployment.

Each client deployment is configured for the operator's own property, policies, inventory, payment account, email domain, and branding. The application does not ship with a shared property catalog or fixed client data.

## Client branding

Set `VITE_CLIENT_NAME` to the property or operating company name. Set `VITE_CLIENT_LOGO` to an image path under `public/` when the client has a logo. Without those variables, the interface uses Magrify as the platform brand.

## Production setup

1. Run `npm ci`.
2. Create an isolated Convex deployment and set `VITE_CONVEX_URL`.
3. Set `VITE_MAGRIFY_PROFILE=production`.
4. Configure the client's property, units, rates, policies, staff identities, email provider, and Stripe account in Convex.
5. Set `SITE_URL` and deploy the frontend to Cloudflare Pages or another static host.
6. Run `npm run build` and `npm run typecheck` before publishing.

Magrify created and maintains this platform. The MIT license in `LICENSE` preserves the original copyright and permission notice required for redistributed source.
