"""Offline CDK scaffold. No stack or AWS resources exist in Phase 0."""
import aws_cdk as cdk

app = cdk.App(outdir="cdk.out")
assembly = app.synth()
assert not assembly.stacks, "Phase 0 must not contain deployable stacks"
print("PASS: synthesized empty CDK assembly; no deployable stacks or resources")
