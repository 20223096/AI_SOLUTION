import { postJson } from './client'
import type { components } from './types/api'

type Schemas = components['schemas']
export type AddressCoordinateResponse = Schemas['AddressCoordinateResponse']

export function lookupAddressCoordinate(address: string, selectedAddressId?: string, signal?: AbortSignal) {
  return postJson<AddressCoordinateResponse>(
    '/api/locations/address-coordinate',
    { address, selected_address_id: selectedAddressId ?? null },
    signal,
  )
}
