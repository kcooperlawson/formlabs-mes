// The plant's own name for itself, shared by the login screen and the
// Manager Cockpit's header so they read as one brand rather than two -
// "POURING LOG" for a plant running as a simple logging system, "SCADA
// TERMINAL" once work orders/execution mode are on. Single source of truth
// so the two screens can never drift apart on the wording.
export function brandTitle(simpleMode: boolean) {
  return {
    lead: simpleMode ? 'POURING' : 'SCADA',
    tail: simpleMode ? 'LOG' : 'TERMINAL',
    sub: simpleMode ? 'Resin Pouring · Production Record' : 'Manufacturing Execution System',
  }
}
