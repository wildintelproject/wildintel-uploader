import { api } from './api'
import type { DeploymentFields } from './types'

/** What a created deployment says of itself — its deployment.json, kept in its folder of the collections folder — or null when it is not there. */
export async function readDeployment(researchProjectId: string, deploymentId: string): Promise<DeploymentFields | null> {
  const { path } = await api.collectionPath(researchProjectId, deploymentId)
  const { results } = await api.listLocalDeployments(path)
  return results.find((d) => d.deployment_id === deploymentId) ?? null
}
