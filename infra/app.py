"""Offline CDK scaffold. No stack or AWS resources exist in Phase 0."""
import aws_cdk as cdk

app = cdk.App()
app.synth()
