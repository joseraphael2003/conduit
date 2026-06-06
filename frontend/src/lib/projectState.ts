export type ProjectStateValue =
  | 'created'
  | 'step_1_complete'
  | 'step_2_complete'
  | 'step_3_complete'
  | 'step_4_complete'
  | 'step_5_complete';

export interface ProjectState {
  state: ProjectStateValue;
}

export function isStepComplete(
  projectState: ProjectState | null,
  step: number
): boolean {
  if (!projectState) return false;
  const stateMap: Record<ProjectStateValue, number> = {
    created: 0,
    step_1_complete: 1,
    step_2_complete: 2,
    step_3_complete: 3,
    step_4_complete: 4,
    step_5_complete: 5,
  };
  const completedSteps = stateMap[projectState.state] ?? 0;
  return step <= completedSteps;
}
