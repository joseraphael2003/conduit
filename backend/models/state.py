from enum import Enum

class ProjectState(str, Enum):
    CREATED = "created"
    STEP_1_COMPLETE = "step_1_complete"
    STEP_2_COMPLETE = "step_2_complete"
    STEP_3_COMPLETE = "step_3_complete"
    STEP_4_COMPLETE = "step_4_complete"
    STEP_5_COMPLETE = "step_5_complete"
