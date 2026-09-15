import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { notesApi } from '../api/notes'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { fl } from '../theme'

const input = `${fl.input} flex-1 py-3 text-base font-normal text-[#F8FAFC]`
const btn = `${fl.btn} px-4 py-3`

// Ported from pages/operator_form/notes_tab.py - a written note for the
// plant lead. "Nobody is watching this in real time" is the original's own
// warning (see that file's docstring on why): this is a record, not a
// live channel.
export function NotesTab() {
  const queryClient = useQueryClient()
  const asOperator = useDebugOperator()
  const notesQuery = useQuery({ queryKey: ['notes', asOperator], queryFn: () => notesApi.list(asOperator) })
  const [draft, setDraft] = useState('')

  const sendMutation = useMutation({
    mutationFn: (message: string) => notesApi.send(message, asOperator),
    onSuccess: () => {
      setDraft('')
      queryClient.invalidateQueries({ queryKey: ['notes', asOperator] })
    },
  })

  const notes = notesQuery.data ?? []

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-[#CBD5E1]">📋 Notes</h3>
      <p className={`text-sm ${fl.muted}`}>
        A written note for the plant lead — it stays on the record with your name and the time on it.
      </p>
      <p className="rounded-lg border border-amber-800 bg-amber-950 px-3 py-2 text-sm text-amber-200">
        <strong>Nobody is watching this in real time.</strong> Use the radio or find a lead in person
        for anything urgent or unsafe. This is for things that would otherwise be forgotten by the
        end of shift.
      </p>

      <div className={`flex h-80 flex-col gap-2 overflow-y-auto ${fl.card}`}>
        {notes.length === 0 ? (
          <p className={`text-sm ${fl.muted}`}>
            Nothing noted yet. Anything you write here is kept with your name and the time.
          </p>
        ) : (
          notes.map((n, i) => (
            <div key={i} className={`flex gap-2 ${n.is_manager_reply ? '' : 'flex-row-reverse'}`}>
              <span className="text-lg">{n.is_manager_reply ? '👨‍💼' : '👷'}</span>
              <div
                className={
                  n.is_manager_reply
                    ? 'rounded-lg bg-[#0F172A] px-3 py-2 text-sm text-[#F8FAFC]'
                    : 'rounded-lg bg-[#EA580C]/15 border border-[#EA580C]/40 px-3 py-2 text-sm text-[#F8FAFC]'
                }
              >
                <p className={`text-xs ${fl.muted}`}>
                  {n.sender_name} · {new Date(n.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                </p>
                <p>{n.message}</p>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="flex gap-2">
        <input
          className={input}
          placeholder="Write a note for management…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && draft.trim()) sendMutation.mutate(draft.trim())
          }}
        />
        <button className={btn} disabled={!draft.trim() || sendMutation.isPending} onClick={() => sendMutation.mutate(draft.trim())}>
          Send
        </button>
      </div>
    </div>
  )
}
