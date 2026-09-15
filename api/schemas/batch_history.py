from pydantic import BaseModel


class BatchTotals(BaseModel):
    fillings_in_window: int
    sitting_now: int
    waiting_qc: int
    avg_qc_turnaround_h: float | None
    avg_time_in_vessel_h: float | None
    longest_sitting_h: float | None
    longest_qc_wait_h: float | None
    no_qc_recorded: int


class DwellByVessel(BaseModel):
    reactor_name: str
    avg_hours: float


class QcTrendPoint(BaseModel):
    day: str
    avg_hours: float


class OutAtQc(BaseModel):
    id: int
    reactor_name: str
    resin_type: str
    hours_at_qc: float


class BatchRow(BaseModel):
    id: int
    reactor_name: str
    resin_type: str
    filled_at: str | None
    emptied_at: str | None
    hours_in_reactor: float | None
    qc_sent_at: str | None
    qc_result_at: str | None
    hours_at_qc: float | None
    qc_result: str
    qc_note: str
    qc_by: str
    open: bool
    qc_open: bool


class BatchHistoryOut(BaseModel):
    totals: BatchTotals
    dwell_by_vessel: list[DwellByVessel]
    qc_trend: list[QcTrendPoint]
    out_at_qc: list[OutAtQc]
    batches: list[BatchRow]
    can_manage_qc: bool


class SetBatchQcRequest(BaseModel):
    sent_at: str
    result_at: str | None = None
    result: str = ""
    note: str = ""
