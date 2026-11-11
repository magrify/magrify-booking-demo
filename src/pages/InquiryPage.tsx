import { FormEvent, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery } from 'convex/react';

import { api } from '../../convex/_generated/api';
import { Spinner } from '../components/Spinner';
import { NotFoundPage } from './NotFoundPage';

export function InquiryPage() {
  const { propertySlug } = useParams<{ propertySlug: string }>();
  const property = useQuery(api.properties.bySlug, propertySlug ? { slug: propertySlug } : 'skip');
  const createInquiry = useMutation(api.inquiries.create);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!propertySlug) return <NotFoundPage />;
  if (property === undefined) return <Spinner label="Loading inquiry form…" />;
  if (property === null) return <NotFoundPage />;
  const slug = propertySlug;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await createInquiry({
        propertySlug: slug,
        channel: 'website',
        name: String(form.get('name') ?? ''),
        email: String(form.get('email') ?? ''),
        phone: String(form.get('phone') ?? ''),
        message: String(form.get('message') ?? ''),
        checkIn: String(form.get('checkIn') ?? '') || undefined,
        checkOut: String(form.get('checkOut') ?? '') || undefined,
        adults: Number(form.get('adults') ?? 1),
        children: Number(form.get('children') ?? 0),
        marketingOptIn: form.get('marketingOptIn') === 'on',
        source: new URLSearchParams(window.location.search).get('utm_source') || 'website',
      });
      window.localStorage.setItem('magrify.pending.inquiry', String(result.inquiryId));
      setSubmitted(true);
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'We could not send the inquiry. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="card mx-auto max-w-2xl p-8 text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Inquiry received</p>
        <h1 className="mt-2 text-3xl font-semibold text-stone-900">We’ll help you find the right stay.</h1>
        <p className="mt-3 text-stone-600">A team member can follow up with availability and a direct booking path for {property.name}.</p>
        <Link to={`/p/${property.slug}`} className="btn-primary mt-6 inline-flex">Check availability now</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <Link to={`/p/${property.slug}`} className="text-sm text-emerald-700 hover:text-emerald-900">← Back to {property.name}</Link>
        <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Questions before booking</p>
        <h1 className="mt-2 text-3xl font-semibold text-stone-900">Tell us what you need</h1>
        <p className="mt-2 text-stone-600">Share your dates, party size, or a question. We’ll qualify the request and help you move into live availability.</p>
      </div>
      <form className="card grid gap-4 p-6" onSubmit={(event) => void submit(event)}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label><span className="field-label">Name</span><input className="field-input" name="name" autoComplete="name" required /></label>
          <label><span className="field-label">Email</span><input className="field-input" name="email" type="email" autoComplete="email" required /></label>
        </div>
        <label><span className="field-label">Phone</span><input className="field-input" name="phone" type="tel" autoComplete="tel" required /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label><span className="field-label">Check-in (optional)</span><input className="field-input" name="checkIn" type="date" /></label>
          <label><span className="field-label">Check-out (optional)</span><input className="field-input" name="checkOut" type="date" /></label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label><span className="field-label">Adults</span><input className="field-input" name="adults" type="number" min="1" max="50" defaultValue="1" /></label>
          <label><span className="field-label">Children</span><input className="field-input" name="children" type="number" min="0" max="50" defaultValue="0" /></label>
        </div>
        <label><span className="field-label">What can we help with?</span><textarea className="field-input min-h-28 resize-y" name="message" maxLength={2000} required placeholder="Tell us about your dates, rig, room, accessibility needs, or question…" /></label>
        <label className="flex items-start gap-2 text-sm text-stone-600"><input className="mt-1" name="marketingOptIn" type="checkbox" /> Send me occasional stay updates and offers.</label>
        {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p> : null}
        <button type="submit" className="btn-primary" disabled={submitting}>{submitting ? 'Sending…' : 'Send inquiry'}</button>
      </form>
    </div>
  );
}
