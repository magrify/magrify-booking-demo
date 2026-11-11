import { useState } from 'react';
import { useMutation, useQuery } from 'convex/react';

import { api } from '../../convex/_generated/api';
import { useAdminProperty } from '../components/AdminShell';
import { Spinner } from '../components/Spinner';

export function AdminInquiriesPage() {
  const { property } = useAdminProperty();
  const [filter, setFilter] = useState<'all' | 'new' | 'qualified' | 'booking_started' | 'converted' | 'closed'>('all');
  const [message, setMessage] = useState('');
  const rows = useQuery(api.inquiries.listForStaff, {
    propertyId: property.propertyId,
    ...(filter === 'all' ? {} : { status: filter }),
  });
  const qualify = useMutation(api.inquiries.qualify);
  const setAgentApproval = useMutation(api.inquiries.setAgentApproval);

  async function update(inquiryId: string, status: 'qualified' | 'closed') {
    setMessage('');
    try {
      await qualify({ propertyId: property.propertyId, inquiryId: inquiryId as never, status, qualificationNote: status === 'qualified' ? 'Qualified by staff for availability follow-up.' : 'Closed by staff.' });
      setMessage('Inquiry updated.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Inquiry update failed.');
    }
  }

  async function approveAgent(inquiryId: string, approved: boolean) {
    setMessage('');
    try {
      await setAgentApproval({ propertyId: property.propertyId, inquiryId: inquiryId as never, approved });
      setMessage(approved ? 'Agent run approved.' : 'Agent run rejected.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Agent approval failed.');
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">Guest acquisition</p><h1 className="mt-1 text-2xl font-semibold">Inquiries</h1><p className="mt-1 text-sm text-stone-600">Qualify website, chat, and phone requests before they enter the booking funnel.</p></div>
        <select className="field-input w-auto" value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)} aria-label="Filter inquiries">
          <option value="all">All statuses</option><option value="new">New</option><option value="qualified">Qualified</option><option value="booking_started">Booking started</option><option value="converted">Converted</option><option value="closed">Closed</option>
        </select>
      </div>
      {message ? <p className="rounded-lg bg-stone-900 px-4 py-3 text-sm text-white" role="status">{message}</p> : null}
      {rows === undefined ? <Spinner label="Loading inquiries…" /> : rows.length === 0 ? <div className="card p-8 text-center text-stone-500">No inquiries match this filter.</div> : <div className="space-y-3">{rows.map((row) => <article key={row.inquiryId} className="card p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold text-stone-900">{row.name}</h2><p className="text-sm text-stone-500">{row.email} · {row.phone} · {row.channel}</p></div><span className="badge">{row.status.replaceAll('_', ' ')}</span></div><p className="mt-3 text-sm text-stone-700">{row.message}</p><p className="mt-2 text-xs text-stone-500">{row.checkIn && row.checkOut ? `${row.checkIn} → ${row.checkOut}` : 'No dates supplied'} · CRM {row.deskcommStatus} · follow-up {row.followUpStatus} · agent {row.agentStatus}</p>{row.agentStatus === 'awaiting_approval' ? <div className="mt-4 flex gap-2"><button type="button" className="btn-primary" onClick={() => void approveAgent(row.inquiryId, true)}>Approve agent</button><button type="button" className="btn-secondary" onClick={() => void approveAgent(row.inquiryId, false)}>Reject agent</button></div> : null}{row.status === 'new' ? <div className="mt-4 flex gap-2"><button type="button" className="btn-primary" onClick={() => void update(row.inquiryId, 'qualified')}>Qualify & follow up</button><button type="button" className="btn-secondary" onClick={() => void update(row.inquiryId, 'closed')}>Close</button></div> : null}</article>)}</div>}
    </div>
  );
}
