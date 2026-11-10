import { useEffect } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { Mountain } from 'lucide-react';

/** Production chrome contains no public-showcase or experimental-rail copy. */
export function ProductionAppLayout() {
  const clientName = import.meta.env.VITE_CLIENT_NAME || 'Magrify';
  const clientLogo = import.meta.env.VITE_CLIENT_LOGO;
  useEffect(() => {
    document.title = clientName === 'Magrify' ? 'Magrify Booking Platform' : `${clientName} | Book direct`;
    const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (favicon && clientLogo) favicon.href = clientLogo;
  }, [clientName, clientLogo]);
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <Link to="/" className="flex items-center gap-2 text-stone-900">
            {clientLogo ? <img src={clientLogo} alt={`${clientName} logo`} className="h-12 w-auto max-w-44 object-contain" /> : <><Mountain className="h-6 w-6 text-emerald-700" strokeWidth={2} aria-hidden="true" /><span className="font-display text-lg font-semibold">{clientName}</span></>}
          </Link>
          <nav aria-label="Primary" className="flex items-center gap-3 text-sm">
            <Link to="/admin" className="text-xs text-stone-500 hover:text-stone-800">Staff</Link>
          </nav>
        </div>
      </header>
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-stone-200 py-6 text-center text-xs text-stone-400">
        <><p>
          Booking and property operations by{' '}
          <a href="https://magrify.com" target="_blank" rel="noreferrer" className="font-semibold text-emerald-700 hover:text-emerald-800">
            Magrify
          </a>
        </p>
        <p className="mt-1.5 space-x-3">
          <Link to="/about" className="hover:text-stone-600">About</Link>
          <a href="https://github.com/magrify/magrify-booking-platform" target="_blank" rel="noreferrer" className="hover:text-stone-600">Magrify platform</a>
        </p>
      </>
      </footer>
    </div>
  );
}
