"""Keep default templates deployable in new accounts with low concurrency quotas."""
import jsii
from aws_cdk import IAspect
from aws_cdk import aws_lambda as lam


@jsii.implements(IAspect)
class UnreservedLambda:
    def visit(self, node):
        if isinstance(node, lam.CfnFunction):
            node.add_property_deletion_override("ReservedConcurrentExecutions")
