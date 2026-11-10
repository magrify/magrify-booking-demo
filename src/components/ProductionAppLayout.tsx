import { useEffect } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { Mountain } from 'lucide-react';

/** Production chrome contains no public-showcase or experimental-rail copy. */
export function ProductionAppLayout() {
  const magrifyDemo = import.meta.env.VITE_MAGRIFY_DEMO === 'true';
  const clientName = import.meta.env.VITE_CLIENT_NAME || 'Woodland RV Resort & Campground';
  const clientLogo = import.meta.env.VITE_CLIENT_LOGO || '/woodland-logo.jpg';
  useEffect(() => {
    if (!magrifyDemo) return;
    document.title = `${clientName} | Booking Demo by Magrify`;
    const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (favicon) favicon.href = clientLogo;
  }, [magrifyDemo, clientName, clientLogo]);
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <Link to="/" className="flex items-center gap-2 text-stone-900">
            {magrifyDemo ? <img src={clientLogo} alt={`${clientName} logo`} className="h-12 w-auto max-w-44 object-contain" /> : <><Mountain className="h-6 w-6 text-emerald-700" strokeWidth={2} aria-hidden="true" /><span className="font-display text-lg font-semibold">Magrify</span></>}
          </Link>
          <nav aria-label="Primary" className="flex items-center gap-3 text-sm">
            {!magrifyDemo && <Link to="/admin" className="text-xs text-stone-500 hover:text-stone-800">Staff</Link>}
          </nav>
        </div>
      </header>
      {magrifyDemo && <div className="bg-amber-100 px-4 py-3 text-center text-sm font-semibold text-amber-950">Magrify example demo · Sample inventory and reservations · No real booking or payment</div>}
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-stone-200 py-6 text-center text-xs text-stone-400">
        {magrifyDemo ? <p>Booking experience by <a href="https://magrify.com" className="font-semibold text-emerald-700 hover:text-emerald-800">Magrify</a> · Example demo only</p> : <><p>
          Powered by <span className="font-semibold text-stone-500">Magrify</span> — open-source
          property management by{' '}
          <a href="https://magrify.com" target="_blank" rel="noreferrer" className="font-semibold text-emerald-700 hover:text-emerald-800">
            Magrify
          </a>
        </p>
        <p className="mt-1.5 space-x-3">
          <Link to="/about" className="hover:text-stone-600">About</Link>
          <a href="https://github.com/magrify/magrify-booking-demo" target="_blank" rel="noreferrer" className="hover:text-stone-600">Open-source project</a>
        </p></>}
      </footer>
    </div>
  );
}
