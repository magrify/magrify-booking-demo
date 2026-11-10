# Magrify Booking Demo

A client-branded lodging reservation demo by Magrify. The Woodland RV example uses sample inventory and simulated confirmations; it does not reserve real sites or collect payments.

## Branding a client deployment

Set `VITE_MAGRIFY_DEMO=true`, `VITE_CLIENT_NAME`, and `VITE_CLIENT_LOGO` (the path to an image in `public/`). The production UI uses those settings for the logo and page title. Keep the demo notice until a real property authorizes bookings and its actual inventory, payment account, and policies are configured.

## Local build

1. Run `npm ci`.
2. Configure `VITE_CONVEX_URL` for an isolated Convex deployment.
3. Set `VITE_MAGRIFY_PROFILE=production` and the client branding variables.
4. Run `npm run build`.

The MIT license in `LICENSE` retains the original copyright notice required for redistributed source. Magrify branding applies to the guest interface and this fork.
