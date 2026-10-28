from pydantic import BaseModel


class Interval(BaseModel):
    lower: float
    upper: float
