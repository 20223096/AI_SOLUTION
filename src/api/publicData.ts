import { request } from './client'
import type { components } from './types/api'

export type PublicDataCatalog = components['schemas']['PublicDataCatalogResponse']

export function getPublicDataCatalog(signal?: AbortSignal) {
  return request<PublicDataCatalog>('/api/public-data/catalog', { signal })
}
