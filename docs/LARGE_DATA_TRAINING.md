# Large-data training and SageMaker configuration

## Actual result — 11 October 2026

Downloaded the official UCI Beijing Multi-Site Air Quality archive, CC BY 4.0:
[dataset and license](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data).
Attribution: Chen, S. (2017), DOI:10.24432/C5RK5G. Real hourly observations from twelve Beijing
stations, March 2013–February 2017. This is **not Delhi training data**.

420,768 input rows; 8,739 missing/invalid PM2.5 rows. No values interpolated or fabricated.
Chronological global splits: train 245,633; validation 81,546; test 81,979.
One-hour labels crossing split boundaries are purged. Station lags require exact hourly timestamps;
rolling means use current/past values only. The imputer fits training data only. Missing coordinates
and humidity stay missing. Weather is same-hour historical weather, never future observations.

| Model | Test MAE µg/m³ | Test RMSE µg/m³ | Test mean bias µg/m³ |
| --- | ---: | ---: | ---: |
| Persistence | 10.09034 | 19.56450 | -0.03120 |
| Random Forest, selected using validation MAE | 9.75243 | 18.71309 | 0.18503 |
| HistGradientBoosting | 9.87563 | 19.47162 | 0.24312 |

Actual local CPU training and serialized-model re-evaluation completed. Full station metrics,
dates, dependency versions and artifact hashes: [training report](../examples/ml/uci-beijing-training-report.json).
No archived issued provider forecasts exist in this dataset: that baseline is unavailable.
There is no calibrated interval. Recorded-hour availability is a retrospective assumption: actual
publication delays/revisions are unknown. This experiment is unverified for navigation even though
the selected model beats persistence on this test cohort. No Delhi, current-season or street-level
accuracy is established. No SageMaker job/endpoint was launched.

## Reproduce locally (PowerShell, repository root)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
.\.venv\Scripts\python.exe scripts/prepare_training_data.py --download
.\.venv\Scripts\python.exe scripts/train.py --prepared-dir work/ml/experiments/datasets/104865c0a7aa9e924b0e8293 --output work/ml/experiments/models
.\.venv\Scripts\python.exe scripts/evaluate.py --dataset work/ml/experiments/datasets/104865c0a7aa9e924b0e8293 --models work/ml/experiments/models --model-version c72e274c84d4a4bad246d4d6
```

The first command installs numerical dependencies; already installed in this workspace. Dataset/model
versions depend on source bytes and artifact bytes; use the actual printed directories/version if
upstream changes. A preparation rerun refuses to overwrite an existing dataset; reuse the completed
directory. All raw archives, Parquet and model binaries stay in ignored `work/ml/experiments/`.
Only the non-personal evaluation report is committed.

Optional synthetic stress-test preparation, already exercised for 100,000 generated rows:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_training_data.py --source synthetic --records 100000 --stations 8 --seed 42
```

These correlated/noisy scenarios test schema, scale, missing hours and serialization. They are
not calibrated real-world distributions or pollution measurements. Every manifest names the
synthetic source; the trainer, model selector and cloud publication gate block navigation promotion.
The synthetic dataset was prepared, not used for the reported real-data model metrics.

## Current AWS checks and exact missing prerequisites

Account `112920804206`, Mumbai `ap-south-1`, non-root profile `dev-admin` verified.
Existing resources reused:

- ML bucket: `ecorouteml-mlartifacts1dd2d62f-yvrmeewrkgxo`.
- ECR: `112920804206.dkr.ecr.ap-south-1.amazonaws.com/ecoroute-ai-ml-training`.
- Training role: `arn:aws:iam::112920804206:role/EcoRouteML-TrainingRoleAA3C7BE5-VsLKeITwcvc0`.

Read-only preflight verified `ml.m5.large` **training quota = 0**. Docker Linux engine is unavailable;
no actual image digest is configured. `iam:GetRole` is denied, so role trust was not independently
verified (the CDK definition trusts SageMaker). S3 job-input upload, ECR push and operator job-launch
permissions have not been exercised. There is still no deployment-eligible Delhi dataset: the
existing curated pipeline has five measured PM2.5 rows and zero eligible hourly training samples.

1. AWS Console → region **Mumbai** → Service Quotas → AWS services → Amazon SageMaker AI →
   search **ml.m5.large for training job usage** → request account-level quota **1**. Wait for approval.
   CLI verification below. If AWS refuses because of the Free account plan, ask Support about service
   eligibility; do not upgrade or create a different paid instance automatically.
2. Console → IAM → Roles → the exact training role above → Trust relationships. Verify the service
   principal `sagemaker.amazonaws.com` and `sts:AssumeRole`. Required role policy grants are in
   `infra/ml_roles.py`: `s3:ListBucket` limited to datasets/models prefixes; `s3:GetObject` on
   `datasets/*`; `s3:PutObject` on `models/training/*`; exact-repository ECR pull actions;
   regional `ecr:GetAuthorizationToken` (resource-level ARN unsupported); CloudWatch write actions
   on `/aws/sagemaker/TrainingJobs`. Respect the existing workload permissions boundary.
3. Ask your authorized IAM administrator to give the operator `iam:GetRole` on this role, scoped
   S3 dataset upload, exact-repository ECR push/DescribeImages, and `iam:PassRole` on **this role only**
   with `iam:PassedToService=sagemaker.amazonaws.com`. Job actions: `sagemaker:CreateTrainingJob`,
   `DescribeTrainingJob`, `StopTrainingJob`, `AddTags`, `ListTags` restricted to
   `arn:aws:sagemaker:ap-south-1:112920804206:training-job/ecoroute-*`. Quota read uses
   `service-quotas:GetServiceQuota`; quota requests need `RequestServiceQuotaIncrease`. No
   AdministratorAccess, root access keys or endpoint-creation permissions required.
4. Start Docker Desktop → Linux containers. Build and test the existing `Dockerfile.ml` locally.
   Log in to project ECR using your CLI profile, push a versioned tag, then query the real digest.
   Keep the resulting digest-pinned URI in ignored deployment context; it is a non-secret identifier.
5. Upload a reviewed, hash-validated dataset using `scripts/upload_ml_dataset.py`. Account identity
   and exact bucket ownership are checked; SSE and no-overwrite writes are used. For this foreign
   experiment, manual isolated training is possible after approval, but the production workflow
   deliberately rejects it before creating a job and never publishes it to the navigation registry.
6. Generate `scripts/sagemaker_plan.py` with actual bucket/version/role/digest and review costs.
   Obtain separate approval **before** `aws sagemaker create-training-job`. Existing serverless approval
   excluded paid training. Do not configure any real-time endpoint or enable training schedules.
7. For operational Delhi predictions, collect licensed Delhi station history with actual availability
   timestamps, pass chronological and per-station baseline gates, publish through the reviewed
   workflow, and deploy the optional container Lambda inference worker. Configure its ARN on Core.
   Frontend → Route factors & forecasts → sign in → Check station forecast availability. Only approved
   one-hour station models are selectable. `/routes/predict` returns full genuine route geometry;
   predictions match within 1km/±30min, otherwise separately labeled provider data or unavailable.

Verification (no secret values printed):

```powershell
aws sts get-caller-identity --profile dev-admin
aws service-quotas get-service-quota --service-code sagemaker --quota-code L-611FA074 --profile dev-admin --region ap-south-1
.\.venv\Scripts\python.exe scripts/check_sagemaker_ready.py --profile dev-admin --account 112920804206 --region ap-south-1 --role-arn arn:aws:iam::112920804206:role/EcoRouteML-TrainingRoleAA3C7BE5-VsLKeITwcvc0 --dataset work/ml/experiments/datasets/104865c0a7aa9e924b0e8293
docker info --format '{{.ServerVersion}}'
docker build -f Dockerfile.ml -t ecoroute-ml:training .
aws ecr get-login-password --region ap-south-1 --profile dev-admin | docker login --username AWS --password-stdin 112920804206.dkr.ecr.ap-south-1.amazonaws.com
docker tag ecoroute-ml:training 112920804206.dkr.ecr.ap-south-1.amazonaws.com/ecoroute-ai-ml-training:training-v1
docker push 112920804206.dkr.ecr.ap-south-1.amazonaws.com/ecoroute-ai-ml-training:training-v1
aws ecr describe-images --repository-name ecoroute-ai-ml-training --image-ids imageTag=training-v1 --profile dev-admin --region ap-south-1 --query 'imageDetails[0].imageDigest' --output text
```

The preflight always reports launch approval/operator grants as unresolved because it cannot infer
approval or prove all effective IAM policies from metadata. A blocked result is intentional.
Never put AWS credentials, numerical model binaries, provider keys or training credentials in VITE_
variables. SageMaker uses the execution role; there is no SageMaker API key to add in Amplify.

## Costs and cleanup

Official [AWS Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonSageMaker/current/ap-south-1/index.json)
retrieved 11 October 2026, publication 9 October: standard Mumbai `ml.m5.large-Training`
**$0.121/hour**. At 15 minutes, runtime compute arithmetic is **$0.03025** for one instance.
This is not the total bill or a spending cap: startup/billable duration, EBS, S3, ECR retention,
CloudWatch, workflow requests and taxes can add charges. Credit eligibility/Free-plan service access
must be checked in Billing. Repeated jobs cost repeatedly; no hyperparameter search or automatic retry.
The existing job spec sets max runtime 900s/max pending 1800s, one instance, network isolation,
profiler disabled, no GPU, no NAT gateway and no persistent endpoint.
[AWS training API](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTrainingJob.html).

Stop a running approved job with `aws sagemaker stop-training-job --training-job-name ACTUAL_JOB_NAME
--profile dev-admin --region ap-south-1`. Completed jobs have no continuing training compute; retained
S3/ECR/logs can still cost money. Delete only the experiment's reviewed S3 prefix/image digest after
saving required evidence. Never delete the shared ML bucket or other models to clean up one experiment.
Follow the existing infrastructure cleanup guide for complete project teardown. Budgets alert;
they do not hard-cap spending.
