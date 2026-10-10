"""Optional runtimes for the SAME FastAPI app, Cognito pool and data resources."""
import shlex

from aws_cdk import CfnOutput, Fn, RemovalPolicy, Stack
from aws_cdk import aws_apprunner as apprunner
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as alarm_actions
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_eks as eks
from aws_cdk import aws_elasticloadbalancingv2 as elb
from aws_cdk import aws_elasticloadbalancingv2_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lightsail as lightsail
from aws_cdk import aws_logs as logs


class ComputeStack(Stack):
    def __init__(self, scope, name, *, core, options, **kwargs):
        super().__init__(scope, name, **kwargs)
        runtime = options.runtime
        if runtime == "lambda":
            raise ValueError("Lambda is already in Core")
        if runtime == "lightsail-proxy":
            service = lightsail.CfnContainer(self, "Proxy", service_name="ecoroute-proxy", power="micro", scale=1,
                container_service_deployment=lightsail.CfnContainer.ContainerServiceDeploymentProperty(
                    containers=[lightsail.CfnContainer.ContainerProperty(container_name="proxy", image=options.image_uri,
                        command=["uvicorn", "ecoroute.edge:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"],
                        environment=[lightsail.CfnContainer.EnvironmentVariableProperty(variable="UPSTREAM_API_ORIGIN", value=options.api_gateway_origin)],
                        ports=[lightsail.CfnContainer.PortInfoProperty(port="8000", protocol="HTTP")])],
                    public_endpoint=lightsail.CfnContainer.PublicEndpointProperty(container_name="proxy", container_port=8000,
                        health_check_config=lightsail.CfnContainer.HealthCheckConfigProperty(path="/healthz", success_codes="200"))))
            CfnOutput(self, "RuntimeUrl", value=service.attr_url)
            CfnOutput(self, "RuntimeStatus", value="HTTPS proxy to existing Cognito API; not a device bridge or AWS-credential container")
            return
        # The container copies the exact scoped API permissions, never the collector/device roles.
        principal = {"ecs-fargate": "ecs-tasks.amazonaws.com", "ec2": "ec2.amazonaws.com",
                     "apprunner": "tasks.apprunner.amazonaws.com", "eks": "pods.eks.amazonaws.com"}[runtime]
        trust = iam.ServicePrincipal(principal, conditions={"StringEquals": {
            "aws:RequestTag/kubernetes-namespace": "ecoroute", "aws:RequestTag/kubernetes-service-account": "backend"}}) if runtime == "eks" else iam.ServicePrincipal(principal)
        self.role = iam.Role(self, "BackendRole", assumed_by=trust,
            inline_policies={"ExistingApiAccess": core.runtime_policy_document})
        if runtime == "eks":
            self.role.assume_role_policy.add_statements(iam.PolicyStatement(
                actions=["sts:TagSession"], principals=[trust]))
        environment = core.runtime_environment
        image, digest = options.image_uri.split("@", 1)
        registry, repository_name = image.split("/", 1)
        if registry != f"{self.account}.dkr.ecr.{self.region}.amazonaws.com":
            raise ValueError("Runtime image must be in the selected account and region")
        repository = ecr.Repository.from_repository_name(self, "ImageRepository", repository_name)
        if runtime == "apprunner":
            pull = iam.Role(self, "ImagePullRole", assumed_by=iam.ServicePrincipal("build.apprunner.amazonaws.com"))
            repository.grant_pull(pull)
            scaling = apprunner.CfnAutoScalingConfiguration(self, "BoundedScaling", max_size=1, min_size=1, max_concurrency=10)
            service = apprunner.CfnService(self, "FastApi", auto_scaling_configuration_arn=scaling.attr_auto_scaling_configuration_arn,
                instance_configuration=apprunner.CfnService.InstanceConfigurationProperty(cpu="256", memory="512", instance_role_arn=self.role.role_arn),
                health_check_configuration=apprunner.CfnService.HealthCheckConfigurationProperty(protocol="HTTP", path="/api/v1/health"),
                source_configuration=apprunner.CfnService.SourceConfigurationProperty(auto_deployments_enabled=False,
                    authentication_configuration=apprunner.CfnService.AuthenticationConfigurationProperty(access_role_arn=pull.role_arn),
                    image_repository=apprunner.CfnService.ImageRepositoryProperty(image_identifier=options.image_uri, image_repository_type="ECR",
                        image_configuration=apprunner.CfnService.ImageConfigurationProperty(port="8000",
                            runtime_environment_variables=[apprunner.CfnService.KeyValuePairProperty(name=k, value=v) for k, v in environment.items()]))))
            CfnOutput(self, "RuntimeUrl", value=Fn.join("", ["https://", service.attr_service_url]))
            return
        vpc = ec2.Vpc(self, "RuntimeVpc", max_azs=2, nat_gateways=0,
                      subnet_configuration=[ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC)])
        if runtime == "eks":
            cluster_name = f"ecoroute-{self.account}-{self.region}"
            audit = logs.LogGroup(self, "ClusterAuditLogs", log_group_name=f"/aws/eks/{cluster_name}/cluster",
                retention=logs.RetentionDays.ONE_WEEK, removal_policy=RemovalPolicy.DESTROY)
            cluster_role = iam.Role(self, "ClusterRole", assumed_by=iam.ServicePrincipal("eks.amazonaws.com"),
                managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSClusterPolicy")])
            cluster = eks.CfnCluster(self, "Cluster", name=cluster_name, role_arn=cluster_role.role_arn, version=options.eks_version,
                access_config=eks.CfnCluster.AccessConfigProperty(authentication_mode="API", bootstrap_cluster_creator_admin_permissions=False),
                resources_vpc_config=eks.CfnCluster.ResourcesVpcConfigProperty(subnet_ids=[s.subnet_id for s in vpc.public_subnets],
                    endpoint_private_access=True, endpoint_public_access=True, public_access_cidrs=options.eks_admin_cidrs),
                upgrade_policy=eks.CfnCluster.UpgradePolicyProperty(support_type="STANDARD"),
                logging=eks.CfnCluster.LoggingProperty(cluster_logging=eks.CfnCluster.ClusterLoggingProperty(
                    enabled_types=[eks.CfnCluster.LoggingTypeConfigProperty(type=x) for x in ("api", "audit", "authenticator")])) )
            cluster.node.add_dependency(audit)
            access = eks.CfnAccessEntry(self, "Operator", cluster_name=cluster.ref, principal_arn=options.eks_operator_arn,
                type="STANDARD", access_policies=[eks.CfnAccessEntry.AccessPolicyProperty(
                    policy_arn="arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy",
                    access_scope=eks.CfnAccessEntry.AccessScopeProperty(type="cluster"))])
            access.add_resource_dependency(cluster)
            nodes = iam.Role(self, "NodesRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
                managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name(p) for p in
                    ("AmazonEKSWorkerNodePolicy", "AmazonEC2ContainerRegistryPullOnly", "AmazonEKS_CNI_Policy")])
            # Block pod access to the node role through IMDS; app receives only Pod Identity.
            launch = ec2.CfnLaunchTemplate(self, "NodesTemplate", launch_template_data=ec2.CfnLaunchTemplate.LaunchTemplateDataProperty(
                metadata_options=ec2.CfnLaunchTemplate.MetadataOptionsProperty(http_tokens="required", http_put_response_hop_limit=1),
                block_device_mappings=[ec2.CfnLaunchTemplate.BlockDeviceMappingProperty(device_name="/dev/xvda",
                    ebs=ec2.CfnLaunchTemplate.EbsProperty(encrypted=True, volume_size=20, volume_type="gp3"))]))
            nodegroup = eks.CfnNodegroup(self, "Nodes", cluster_name=cluster.ref, node_role=nodes.role_arn,
                subnets=[s.subnet_id for s in vpc.public_subnets], ami_type="AL2023_x86_64_STANDARD", instance_types=["t3.small"],
                scaling_config=eks.CfnNodegroup.ScalingConfigProperty(min_size=1, desired_size=1, max_size=1),
                launch_template=eks.CfnNodegroup.LaunchTemplateSpecificationProperty(id=launch.ref, version=launch.attr_latest_version_number))
            agent = eks.CfnAddon(self, "PodIdentityAgent", cluster_name=cluster.ref, addon_name="eks-pod-identity-agent")
            agent.add_resource_dependency(nodegroup)
            eks.CfnPodIdentityAssociation(self, "BackendIdentity", cluster_name=cluster.ref, namespace="ecoroute",
                service_account="backend", role_arn=self.role.role_arn)
            CfnOutput(self, "ClusterName", value=cluster.ref)
            CfnOutput(self, "BackendEnvironment", value=Fn.to_json_string(environment))
            CfnOutput(self, "BackendImage", value=options.image_uri)
            CfnOutput(self, "RuntimeStatus", value="Apply generated manifest; ClusterIP only. HTTPS ingress/controller requires separate reviewed configuration")
            return
        group = logs.LogGroup(self, "BackendLogs", retention=logs.RetentionDays.ONE_WEEK,
                              removal_policy=RemovalPolicy.DESTROY)
        certificate = acm.Certificate.from_certificate_arn(self, "Tls", options.regional_certificate_arn)
        if not options.regional_certificate_arn.startswith(f"arn:aws:acm:{self.region}:{self.account}:"):
            raise ValueError("ALB certificate must be in the selected region/account")
        balancer = elb.ApplicationLoadBalancer(self, "Https", vpc=vpc, internet_facing=True)
        listener = balancer.add_listener("Tls", port=443, certificates=[certificate], ssl_policy=elb.SslPolicy.RECOMMENDED_TLS,
                                        open=True)
        if runtime == "ecs-fargate":
            cluster = ecs.Cluster(self, "Cluster", vpc=vpc)
            task = ecs.FargateTaskDefinition(self, "Task", cpu=256, memory_limit_mib=512, task_role=self.role)
            container = task.add_container("FastApi", image=ecs.ContainerImage.from_ecr_repository(repository, digest),
                environment=environment, user="10001", readonly_root_filesystem=True,
                logging=ecs.LogDrivers.aws_logs(stream_prefix="backend", log_group=group))
            container.add_port_mappings(ecs.PortMapping(container_port=8000))
            task.add_volume(name="scratch")
            container.add_mount_points(ecs.MountPoint(container_path="/tmp", source_volume="scratch", read_only=False))
            service = ecs.FargateService(self, "Backend", cluster=cluster, task_definition=task, desired_count=1,
                assign_public_ip=True, vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True), min_healthy_percent=0, max_healthy_percent=100)
            service.connections.allow_from(balancer, ec2.Port.tcp(8000))
            listener.add_targets("FastApi", port=8000, targets=[service],
                health_check=elb.HealthCheck(path="/api/v1/health", healthy_http_codes="200"))
            cpu_alarm = cloudwatch.Alarm(self, "CpuHigh", metric=service.metric_cpu_utilization(), threshold=85, evaluation_periods=3)
        else:
            repository.grant_pull(self.role)
            self.role.add_to_policy(iam.PolicyStatement(actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[group.log_group_arn + ":*"]))
            self.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
            security = ec2.SecurityGroup(self, "BackendSecurity", vpc=vpc)
            security.add_ingress_rule(balancer.connections.security_groups[0], ec2.Port.tcp(8000))
            instance = ec2.Instance(self, "Backend", vpc=vpc, role=self.role, security_group=security,
                instance_type=ec2.InstanceType("t3.small"), require_imdsv2=True,
                machine_image=ec2.MachineImage.latest_amazon_linux2023(),
                block_devices=[ec2.BlockDevice(device_name="/dev/xvda", volume=ec2.BlockDeviceVolume.ebs(16, encrypted=True))])
            instance.instance.add_property_override("MetadataOptions.HttpPutResponseHopLimit", 2)
            # No credentials in user-data; instance role supplies temporary credentials.
            env_text = "\n".join(f"{k}={v}" for k, v in environment.items())
            instance.user_data.add_commands("set -eu", "dnf install -y docker", "systemctl enable --now docker",
                "install -m 600 /dev/null /etc/ecoroute.env",
                "cat > /etc/ecoroute.env <<'ECOROUTE_ENV'\n" + env_text + "\nECOROUTE_ENV",
                f"aws ecr get-login-password --region {self.region} | docker login --username AWS --password-stdin {registry}",
                "docker run -d --restart=unless-stopped --name ecoroute --user 10001 --read-only --tmpfs /tmp "
                f"--env-file /etc/ecoroute.env -p 8000:8000 --log-driver=awslogs --log-opt awslogs-region={self.region} "
                f"--log-opt awslogs-group={group.log_group_name} --log-opt awslogs-stream=backend " + shlex.quote(options.image_uri))
            listener.add_targets("FastApi", port=8000, targets=[targets.InstanceTarget(instance, 8000)],
                health_check=elb.HealthCheck(path="/api/v1/health", healthy_http_codes="200"))
            cpu_alarm = cloudwatch.Alarm(self, "InstanceCpuHigh", metric=cloudwatch.Metric(namespace="AWS/EC2", metric_name="CPUUtilization",
                dimensions_map={"InstanceId": instance.instance_id}), threshold=85, evaluation_periods=3)
        CfnOutput(self, "RuntimeHost", value=balancer.load_balancer_dns_name)
        CfnOutput(self, "RuntimeStatus", value="Create matching certificate DNS alias and verify HTTPS/Cognito before setting backend_origin")
        error_alarm = cloudwatch.Alarm(self, "BackendErrors", metric=balancer.metrics.http_code_target(elb.HttpCodeTarget.TARGET_5XX_COUNT),
                         threshold=1, evaluation_periods=1, treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING)
        for alarm in (cpu_alarm, error_alarm):
            alarm.add_alarm_action(alarm_actions.SnsAction(core.operational_alerts))
