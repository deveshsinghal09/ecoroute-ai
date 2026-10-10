"""Two alternatives serving the existing Vite build; no copied or replacement frontend."""
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_amplify as amplify
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as targets
from aws_cdk import aws_s3 as s3


class HostingStack(Stack):
    def __init__(self, scope, name, *, options, **kwargs):
        super().__init__(scope, name, **kwargs)
        if options.hosting == "amplify":
            app = amplify.CfnApp(self, "Website", name="ecoroute-ai", platform="WEB",
                custom_rules=[amplify.CfnApp.CustomRuleProperty(source="</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|mp4|webm)$)([^.]+$)/>", target="/index.html", status="200")])
            amplify.CfnBranch(self, "Main", app_id=app.attr_app_id, branch_name="main", stage="PRODUCTION", enable_auto_build=False)
            CfnOutput(self, "AmplifyAppId", value=app.attr_app_id)
            CfnOutput(self, "FrontendUrl", value=f"https://main.{app.attr_default_domain}")
            CfnOutput(self, "Status", value="Manual deployment required: publish existing frontend/dist; no repository OAuth token")
            return
        if options.hosting != "cloudfront":
            raise ValueError("Hosting is disabled")
        bucket = s3.Bucket(self, "Frontend", encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED, removal_policy=RemovalPolicy.RETAIN)
        domain = {}
        if options.domain_name:
            domain = {"domain_names": [options.domain_name], "certificate": acm.Certificate.from_certificate_arn(
                self, "GlobalCertificate", options.cloudfront_certificate_arn)}
        # OAC signs requests; website endpoint/public ACLs are deliberately not used.
        distribution = cloudfront.Distribution(self, "Website", default_root_object="index.html",
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            price_class=cloudfront.PriceClass.PRICE_CLASS_200,
            default_behavior=cloudfront.BehaviorOptions(origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS, compress=True,
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED),
            error_responses=[cloudfront.ErrorResponse(http_status=n, response_http_status=200,
                response_page_path="/index.html", ttl=Duration.seconds(0)) for n in (403, 404)], **domain)
        if options.domain_name:
            zone = route53.HostedZone.from_hosted_zone_attributes(self, "Zone", hosted_zone_id=options.hosted_zone_id,
                                                                zone_name=options.hosted_zone_name)
            for kind, name in ((route53.ARecord, "AliasA"), (route53.AaaaRecord, "AliasAAAA")):
                kind(self, name, zone=zone, record_name=options.domain_name,
                     target=route53.RecordTarget.from_alias(targets.CloudFrontTarget(distribution)))
        CfnOutput(self, "FrontendBucket", value=bucket.bucket_name)
        CfnOutput(self, "DistributionId", value=distribution.distribution_id)
        CfnOutput(self, "FrontendUrl", value="https://" + (options.domain_name or distribution.distribution_domain_name))
        CfnOutput(self, "Status", value="Upload frontend/dist after real API/Cognito build configuration; exact CORS/callback update required")
