import { ExternalLink, Github, Mountain } from 'lucide-react';

/** Public about page: what Magrify is and who builds it. */
export function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <div className="card p-8">
        <div className="mb-4 flex items-center gap-2">
          <Mountain className="h-8 w-8 text-emerald-700" strokeWidth={2} />
          <h1 className="font-display text-3xl font-semibold text-stone-900">About Magrify</h1>
        </div>
        <p className="text-stone-600">
          Magrify builds the booking and property operations platform for independent short term
          rental owners and hospitality teams. Guests book directly, while operators manage rates,
          inventory, guests, payments, staff workflows, and channel connections in one system.
        </p>

        <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
          <h2 className="font-display text-lg font-semibold text-emerald-900">Built by Magrify</h2>
          <p className="mt-1.5 text-sm text-emerald-900/80">
            Magrify designs, builds, and supports the platform used by{' '}
            <a
              href="https://magrify.com"
              target="_blank"
              rel="noreferrer"
              className="font-semibold underline hover:text-emerald-950"
            >
              Magrify
            </a>{' '}and its lodging clients.
          </p>
          <a
            href="https://magrify.com"
            target="_blank"
            rel="noreferrer"
            className="btn-primary mt-4 inline-flex items-center gap-1.5"
          >
            Visit magrify.com <ExternalLink className="h-4 w-4" aria-hidden="true" />
          </a>
        </div>

        <div className="mt-6 space-y-2 text-sm text-stone-600">
          <p className="flex items-center gap-2">
            <Github className="h-4 w-4" aria-hidden="true" />
            <a
              href="https://github.com/magrify/magrify-booking-demo"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-stone-900"
            >
              Source on GitHub
            </a>{' '}
            — source maintained by Magrify.
          </p>
          <p className="flex items-center gap-2">
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
            <a
              href="https://magrify.com/"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-stone-900"
            >
              Documentation
            </a>{' '}
            — quickstart, configuration, self-hosting.
          </p>
        </div>
      </div>
    </div>
  );
}
