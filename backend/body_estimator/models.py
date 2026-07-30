from pydantic import BaseModel, Field

class BodyMeasurements(BaseModel):
    shoulderCircumference: float = Field(..., description="Estimated shoulder circumference in cm")
    armLength: float = Field(..., description="Estimated arm length in cm")
    breastCircumference: float = Field(..., description="Estimated breast/chest circumference in cm")
    underBreastCircumference: float = Field(..., description="Estimated under breast circumference in cm")
    innerLegLength: float = Field(..., description="Estimated inner leg (inseam) length in cm")
    waistCircumference: float = Field(..., description="Estimated waist circumference in cm")
    hipCircumference: float = Field(..., description="Estimated hip circumference in cm")
    upperThighCircumference: float = Field(..., description="Estimated upper thigh circumference in cm")
    bicepsCircumference: float = Field(..., description="Estimated biceps circumference in cm")
    collarboneToBellyButtonLength: float = Field(..., description="Estimated collarbone to belly button length in cm")
    footLength: float = Field(..., description="Estimated foot length in cm")
    footWidth: float = Field(..., description="Estimated foot width in cm")
    waistToCrotchFrontLength: float = Field(..., description="Estimated waist to crotch front rise in cm")
    waistToCrotchBackLength: float = Field(..., description="Estimated waist to crotch back rise in cm")

class EstimationResponse(BaseModel):
    measurements: BodyMeasurements
    confidence: float
