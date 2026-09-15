import { createContext, useContext } from 'react'

// The impersonated operator's name while a manager/admin is using Debug
// Mode (see OperatorFormPage's own banner + picker), or undefined for a
// real operator/packer session and for a manager/admin who hasn't picked
// anyone yet. Read by every tab/mutation that would otherwise attribute a
// write to the signed-in user's own name - mirrors Operator_Form.py's
// page-level `current_user`, which every tab down there reads the same way
// instead of the session's own name.
const DebugOperatorContext = createContext<string | undefined>(undefined)

export const DebugOperatorProvider = DebugOperatorContext.Provider

export function useDebugOperator(): string | undefined {
  return useContext(DebugOperatorContext)
}
