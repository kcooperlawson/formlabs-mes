import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { floorCommsApi } from '../api/floorComms'
import { fl } from '../theme'

const input = `${fl.input} flex-1 py-3 text-base font-normal text-[#F8FAFC]`
const btn = `${fl.btn} px-4 py-3`

// Notes from the Floor - the manager side, ported from
// pages/Mgr_Floor_Comms.py. "Nothing here alerts anybody" is the
// original's own caption, kept verbatim: this is read when a manager opens
// the page, not a live channel.
export function FloorCommsPage() {
  const queryClient = useQueryClient()
  const operatorsQuery = useQuery({ queryKey: ['floor-comms', 'operators'], queryFn: floorCommsApi.operators })
  const [selected, setSelected] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const ops = operatorsQuery.data ?? []
  const written = ops.filter((o) => o.has_written)
  const notWritten = ops.filter((o) => !o.has_written)
  const active = selected ?? written[0]?.name ?? notWritten[0]?.name ?? null

  const threadQuery = useQuery({
    queryKey: ['floor-comms', 'thread', active],
    queryFn: () => floorCommsApi.thread(active as string),
    enabled: !!active,
  })

  const replyMutation = useMutation({
    mutationFn: (message: string) => floorCommsApi.reply(active as string, message),
    onSuccess: () => {
      setDraft('')
      queryClient.invalidateQueries({ queryKey: ['floor-comms', 'thread', active] })
      queryClient.invalidateQueries({ queryKey: ['floor-comms', 'operators'] })
    },
  })

  return (
    <div className="flex flex-col gap-3">
      <h1 className={fl.heading}>📋 Notes from the Floor</h1>
      <p className={`text-sm ${fl.muted}`}>
        Written notes from operators, read when you open this page. Nothing here alerts anybody,
        so it is not where an urgent problem will reach you.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[200px_1fr]">
        <div className="flex flex-col gap-1">
          <p className={`text-xs ${fl.muted}`}>● has written ({written.length})</p>
          {[...written, ...notWritten].map((o) => (
            <button
              key={o.name}
              onClick={() => setSelected(o.name)}
              className={`rounded-lg px-2 py-1.5 text-left text-sm ${
                active === o.name
                  ? 'bg-[#0F172A] font-medium text-white'
                  : 'text-[#CBD5E1] hover:bg-[#0F172A]'
              }`}
            >
              {o.has_written ? '●' : '○'} {o.name}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-2">
          {active && <h2 className="text-sm font-semibold text-white">Notes from {active}</h2>}
          <div className={`flex h-80 flex-col gap-2 overflow-y-auto ${fl.card}`}>
            {!active ? (
              <p className={`text-sm ${fl.muted}`}>No operators yet.</p>
            ) : (threadQuery.data ?? []).length === 0 ? (
              <p className={`text-sm ${fl.muted}`}>{active} has not written anything.</p>
            ) : (
              (threadQuery.data ?? []).map((n, i) => (
                <div key={i} className={`flex gap-2 ${n.is_manager_reply ? 'flex-row-reverse' : ''}`}>
                  <span className="text-lg">{n.is_manager_reply ? '👨‍💼' : '👷'}</span>
                  <div
                    className={
                      n.is_manager_reply
                        ? 'rounded-lg bg-[#EA580C]/15 border border-[#EA580C]/40 px-3 py-2 text-sm text-[#F8FAFC]'
                        : 'rounded-lg bg-[#0F172A] px-3 py-2 text-sm text-[#F8FAFC]'
                    }
                  >
                    <p className={`text-xs ${fl.muted}`}>
                      {n.sender_name} ·{' '}
                      {new Date(n.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                    </p>
                    <p>{n.message}</p>
                  </div>
                </div>
              ))
            )}
          </div>

          {active && (
            <div className="flex gap-2">
              <input
                className={input}
                placeholder={`Reply to ${active}…`}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && draft.trim()) replyMutation.mutate(draft.trim())
                }}
              />
              <button
                className={btn}
                disabled={!draft.trim() || replyMutation.isPending}
                onClick={() => replyMutation.mutate(draft.trim())}
              >
                Send
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
