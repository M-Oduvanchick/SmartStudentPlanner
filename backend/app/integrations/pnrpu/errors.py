class PnrpuScheduleError(Exception):
    pass


class ScheduleSourceError(PnrpuScheduleError):
    pass


class InvalidScheduleFileError(PnrpuScheduleError):
    pass


class ScheduleParseError(PnrpuScheduleError):
    pass


class ScheduleGroupNotFoundError(ScheduleParseError):
    pass
