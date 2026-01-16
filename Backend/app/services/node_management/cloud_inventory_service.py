"""
Cloud Dynamic Inventory Service.

Provides dynamic inventory discovery from cloud platforms:
- AWS EC2
- Azure Virtual Machines
- Google Cloud Compute Engine

Supports filtering, tagging, and automatic node registration.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class CloudProviderError(Exception):
    """Base exception for cloud provider errors."""
    pass


class CloudCredentialError(CloudProviderError):
    """Cloud credential validation failed."""
    pass


class CloudDiscoveredNode:
    """Represents a node discovered from a cloud provider."""

    def __init__(
        self,
        instance_id: str,
        name: str,
        private_ip: Optional[str],
        public_ip: Optional[str],
        platform: str,  # linux, windows
        instance_type: str,
        region: str,
        zone: Optional[str] = None,
        state: str = "running",
        tags: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
        cloud_provider: str = "unknown",
        vpc_id: Optional[str] = None,
        subnet_id: Optional[str] = None,
        security_groups: Optional[List[str]] = None,
        launch_time: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.instance_id = instance_id
        self.name = name
        self.private_ip = private_ip
        self.public_ip = public_ip
        self.platform = platform
        self.instance_type = instance_type
        self.region = region
        self.zone = zone
        self.state = state
        self.tags = tags or {}
        self.labels = labels or {}
        self.cloud_provider = cloud_provider
        self.vpc_id = vpc_id
        self.subnet_id = subnet_id
        self.security_groups = security_groups or []
        self.launch_time = launch_time
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "instance_id": self.instance_id,
            "name": self.name,
            "private_ip": self.private_ip,
            "public_ip": self.public_ip,
            "platform": self.platform,
            "instance_type": self.instance_type,
            "region": self.region,
            "zone": self.zone,
            "state": self.state,
            "tags": self.tags,
            "labels": self.labels,
            "cloud_provider": self.cloud_provider,
            "vpc_id": self.vpc_id,
            "subnet_id": self.subnet_id,
            "security_groups": self.security_groups,
            "launch_time": self.launch_time.isoformat() if self.launch_time else None,
            "metadata": self.metadata,
        }

    def to_node_create_data(
        self,
        use_public_ip: bool = False,
        default_ssh_user: Optional[str] = None,
        default_port: int = 22,
    ) -> Dict[str, Any]:
        """Convert to NodeCreate schema data."""
        # Determine host IP
        host = self.public_ip if use_public_ip and self.public_ip else self.private_ip
        if not host:
            raise CloudProviderError(f"No IP address available for instance {self.instance_id}")

        # Determine connection type and defaults based on platform
        if self.platform.lower() == "windows":
            connection_type = "winrm"
            ssh_user = default_ssh_user or "Administrator"
            port = default_port if default_port != 22 else 5986
        else:
            connection_type = "ssh"
            ssh_user = default_ssh_user or self._guess_ssh_user()
            port = default_port

        # Build labels from cloud metadata
        labels = {
            **self.labels,
            "cloud_provider": self.cloud_provider,
            "cloud_region": self.region,
            "cloud_instance_id": self.instance_id,
            "cloud_instance_type": self.instance_type,
        }
        if self.zone:
            labels["cloud_zone"] = self.zone
        if self.vpc_id:
            labels["cloud_vpc_id"] = self.vpc_id

        # Build tags from cloud tags
        tags = list(self.tags.keys()) if self.tags else []
        tags.append(f"cloud:{self.cloud_provider}")
        tags.append(f"region:{self.region}")

        return {
            "name": self._sanitize_name(self.name or self.instance_id),
            "display_name": self.name or self.instance_id,
            "host": host,
            "port": port,
            "connection_type": connection_type,
            "ssh_user": ssh_user,
            "node_type": "compute",
            "labels": labels,
            "tags": tags,
        }

    def _guess_ssh_user(self) -> str:
        """Guess the default SSH user based on platform/AMI."""
        # Common patterns for cloud images
        name_lower = (self.name or "").lower()
        tags_str = str(self.tags).lower()

        if "ubuntu" in name_lower or "ubuntu" in tags_str:
            return "ubuntu"
        elif "amazon" in name_lower or "amzn" in name_lower:
            return "ec2-user"
        elif "centos" in name_lower or "centos" in tags_str:
            return "centos"
        elif "debian" in name_lower or "debian" in tags_str:
            return "admin"
        elif "rhel" in name_lower or "redhat" in name_lower:
            return "ec2-user"
        elif "suse" in name_lower:
            return "ec2-user"
        else:
            return "root"

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use as node name."""
        import re
        # Replace invalid characters with underscore
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "node_" + sanitized
        return sanitized[:255]  # Limit length


class CloudInventoryProvider(ABC):
    """Abstract base class for cloud inventory providers."""

    @abstractmethod
    async def discover_instances(
        self,
        filters: Optional[Dict[str, Any]] = None,
        regions: Optional[List[str]] = None,
    ) -> List[CloudDiscoveredNode]:
        """Discover instances from the cloud provider."""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate cloud provider credentials."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name."""
        pass


class AWSInventoryProvider(CloudInventoryProvider):
    """AWS EC2 inventory provider using boto3."""

    def __init__(
        self,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
        region: str = "us-east-1",
        assume_role_arn: Optional[str] = None,
        profile_name: Optional[str] = None,
    ):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.default_region = region
        self.assume_role_arn = assume_role_arn
        self.profile_name = profile_name
        self._session = None

    def _get_boto3_session(self):
        """Get or create boto3 session."""
        import boto3

        if self._session is None:
            session_kwargs = {}

            if self.profile_name:
                session_kwargs["profile_name"] = self.profile_name
            elif self.access_key_id and self.secret_access_key:
                session_kwargs["aws_access_key_id"] = self.access_key_id
                session_kwargs["aws_secret_access_key"] = self.secret_access_key
                if self.session_token:
                    session_kwargs["aws_session_token"] = self.session_token

            session_kwargs["region_name"] = self.default_region
            self._session = boto3.Session(**session_kwargs)

            # Handle assume role
            if self.assume_role_arn:
                sts = self._session.client("sts")
                assumed = sts.assume_role(
                    RoleArn=self.assume_role_arn,
                    RoleSessionName="noveris-inventory"
                )
                creds = assumed["Credentials"]
                self._session = boto3.Session(
                    aws_access_key_id=creds["AccessKeyId"],
                    aws_secret_access_key=creds["SecretAccessKey"],
                    aws_session_token=creds["SessionToken"],
                    region_name=self.default_region
                )

        return self._session

    def get_provider_name(self) -> str:
        return "aws"

    async def validate_credentials(self) -> bool:
        """Validate AWS credentials by calling STS GetCallerIdentity."""
        try:
            import asyncio
            session = self._get_boto3_session()
            sts = session.client("sts")
            # Run in executor since boto3 is sync
            loop = asyncio.get_event_loop()
            identity = await loop.run_in_executor(None, sts.get_caller_identity)
            logger.info(
                "AWS credentials validated",
                account_id=identity.get("Account"),
                arn=identity.get("Arn")
            )
            return True
        except Exception as e:
            logger.error("AWS credential validation failed", error=str(e))
            raise CloudCredentialError(f"AWS credential validation failed: {e}")

    async def discover_instances(
        self,
        filters: Optional[Dict[str, Any]] = None,
        regions: Optional[List[str]] = None,
    ) -> List[CloudDiscoveredNode]:
        """Discover EC2 instances."""
        import asyncio

        session = self._get_boto3_session()

        # Get list of regions to scan
        if not regions:
            ec2_client = session.client("ec2", region_name=self.default_region)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, ec2_client.describe_regions
            )
            regions = [r["RegionName"] for r in response["Regions"]]

        discovered_nodes = []

        for region in regions:
            try:
                nodes = await self._discover_region(session, region, filters)
                discovered_nodes.extend(nodes)
            except Exception as e:
                logger.warning(
                    "Failed to discover instances in region",
                    region=region,
                    error=str(e)
                )

        logger.info(
            "AWS discovery complete",
            total_instances=len(discovered_nodes),
            regions_scanned=len(regions)
        )

        return discovered_nodes

    async def _discover_region(
        self,
        session,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudDiscoveredNode]:
        """Discover instances in a specific region."""
        import asyncio

        ec2 = session.client("ec2", region_name=region)

        # Build EC2 filters
        ec2_filters = [
            {"Name": "instance-state-name", "Values": ["running", "pending", "stopping"]}
        ]

        if filters:
            # Tag filters
            if "tags" in filters:
                for key, value in filters["tags"].items():
                    ec2_filters.append({
                        "Name": f"tag:{key}",
                        "Values": [value] if isinstance(value, str) else value
                    })

            # VPC filter
            if "vpc_id" in filters:
                ec2_filters.append({
                    "Name": "vpc-id",
                    "Values": [filters["vpc_id"]]
                })

            # Instance type filter
            if "instance_types" in filters:
                ec2_filters.append({
                    "Name": "instance-type",
                    "Values": filters["instance_types"]
                })

        # Paginate through all instances
        loop = asyncio.get_event_loop()
        paginator = ec2.get_paginator("describe_instances")
        pages = paginator.paginate(Filters=ec2_filters)

        nodes = []
        async for page in self._async_paginate(loop, pages):
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    node = self._instance_to_node(instance, region)
                    if node:
                        nodes.append(node)

        return nodes

    async def _async_paginate(self, loop, paginator):
        """Async wrapper for boto3 paginator."""
        import asyncio

        for page in paginator:
            yield page
            await asyncio.sleep(0)  # Yield control

    def _instance_to_node(self, instance: Dict, region: str) -> Optional[CloudDiscoveredNode]:
        """Convert EC2 instance to CloudDiscoveredNode."""
        instance_id = instance.get("InstanceId")
        if not instance_id:
            return None

        # Get name from tags
        tags = {}
        name = instance_id
        for tag in instance.get("Tags", []):
            tags[tag["Key"]] = tag["Value"]
            if tag["Key"] == "Name":
                name = tag["Value"]

        # Determine platform
        platform = "linux"
        if instance.get("Platform", "").lower() == "windows":
            platform = "windows"

        # Get availability zone
        placement = instance.get("Placement", {})
        zone = placement.get("AvailabilityZone")

        # Get security groups
        security_groups = [
            sg.get("GroupId") for sg in instance.get("SecurityGroups", [])
        ]

        return CloudDiscoveredNode(
            instance_id=instance_id,
            name=name,
            private_ip=instance.get("PrivateIpAddress"),
            public_ip=instance.get("PublicIpAddress"),
            platform=platform,
            instance_type=instance.get("InstanceType", "unknown"),
            region=region,
            zone=zone,
            state=instance.get("State", {}).get("Name", "unknown"),
            tags=tags,
            labels={},
            cloud_provider="aws",
            vpc_id=instance.get("VpcId"),
            subnet_id=instance.get("SubnetId"),
            security_groups=security_groups,
            launch_time=instance.get("LaunchTime"),
            metadata={
                "image_id": instance.get("ImageId"),
                "key_name": instance.get("KeyName"),
                "architecture": instance.get("Architecture"),
            }
        )


class AzureInventoryProvider(CloudInventoryProvider):
    """Azure VM inventory provider using azure-mgmt-compute."""

    def __init__(
        self,
        subscription_id: str,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        use_managed_identity: bool = False,
    ):
        self.subscription_id = subscription_id
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.use_managed_identity = use_managed_identity
        self._credential = None

    def _get_credential(self):
        """Get Azure credential."""
        if self._credential is None:
            if self.use_managed_identity:
                from azure.identity import ManagedIdentityCredential
                self._credential = ManagedIdentityCredential()
            elif self.client_id and self.client_secret and self.tenant_id:
                from azure.identity import ClientSecretCredential
                self._credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
            else:
                from azure.identity import DefaultAzureCredential
                self._credential = DefaultAzureCredential()

        return self._credential

    def get_provider_name(self) -> str:
        return "azure"

    async def validate_credentials(self) -> bool:
        """Validate Azure credentials."""
        try:
            import asyncio
            from azure.mgmt.resource import SubscriptionClient

            credential = self._get_credential()
            client = SubscriptionClient(credential)

            loop = asyncio.get_event_loop()
            sub = await loop.run_in_executor(
                None,
                lambda: client.subscriptions.get(self.subscription_id)
            )

            logger.info(
                "Azure credentials validated",
                subscription_id=self.subscription_id,
                subscription_name=sub.display_name
            )
            return True
        except Exception as e:
            logger.error("Azure credential validation failed", error=str(e))
            raise CloudCredentialError(f"Azure credential validation failed: {e}")

    async def discover_instances(
        self,
        filters: Optional[Dict[str, Any]] = None,
        regions: Optional[List[str]] = None,
    ) -> List[CloudDiscoveredNode]:
        """Discover Azure VMs."""
        import asyncio
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.network import NetworkManagementClient

        credential = self._get_credential()
        compute_client = ComputeManagementClient(credential, self.subscription_id)
        network_client = NetworkManagementClient(credential, self.subscription_id)

        loop = asyncio.get_event_loop()

        # Get all VMs
        vms = await loop.run_in_executor(
            None,
            lambda: list(compute_client.virtual_machines.list_all())
        )

        discovered_nodes = []

        for vm in vms:
            # Filter by region
            if regions and vm.location not in regions:
                continue

            # Filter by tags
            if filters and "tags" in filters:
                vm_tags = vm.tags or {}
                match = all(
                    vm_tags.get(k) == v
                    for k, v in filters["tags"].items()
                )
                if not match:
                    continue

            # Get network interface IPs
            private_ip = None
            public_ip = None

            if vm.network_profile and vm.network_profile.network_interfaces:
                for nic_ref in vm.network_profile.network_interfaces:
                    nic_id = nic_ref.id
                    # Extract resource group and NIC name from ID
                    parts = nic_id.split("/")
                    rg_idx = parts.index("resourceGroups") + 1
                    nic_idx = parts.index("networkInterfaces") + 1
                    rg_name = parts[rg_idx]
                    nic_name = parts[nic_idx]

                    try:
                        nic = await loop.run_in_executor(
                            None,
                            lambda: network_client.network_interfaces.get(rg_name, nic_name)
                        )

                        for ip_config in nic.ip_configurations:
                            if ip_config.private_ip_address:
                                private_ip = ip_config.private_ip_address

                            if ip_config.public_ip_address:
                                pub_ip_id = ip_config.public_ip_address.id
                                pub_parts = pub_ip_id.split("/")
                                pub_rg_idx = pub_parts.index("resourceGroups") + 1
                                pub_idx = pub_parts.index("publicIPAddresses") + 1
                                pub_rg = pub_parts[pub_rg_idx]
                                pub_name = pub_parts[pub_idx]

                                pub_ip_obj = await loop.run_in_executor(
                                    None,
                                    lambda: network_client.public_ip_addresses.get(pub_rg, pub_name)
                                )
                                public_ip = pub_ip_obj.ip_address

                            break  # Only get first IP config
                        break  # Only get first NIC
                    except Exception as e:
                        logger.warning(
                            "Failed to get NIC details",
                            nic_id=nic_id,
                            error=str(e)
                        )

            # Determine platform
            platform = "linux"
            if vm.storage_profile and vm.storage_profile.os_disk:
                os_type = vm.storage_profile.os_disk.os_type
                if os_type and os_type.lower() == "windows":
                    platform = "windows"

            # Extract resource group from VM ID
            vm_parts = vm.id.split("/")
            rg_idx = vm_parts.index("resourceGroups") + 1
            resource_group = vm_parts[rg_idx]

            node = CloudDiscoveredNode(
                instance_id=vm.vm_id or vm.name,
                name=vm.name,
                private_ip=private_ip,
                public_ip=public_ip,
                platform=platform,
                instance_type=vm.hardware_profile.vm_size if vm.hardware_profile else "unknown",
                region=vm.location,
                zone=None,  # Azure uses availability sets/zones differently
                state="running",  # Would need to check power state
                tags=vm.tags or {},
                labels={"resource_group": resource_group},
                cloud_provider="azure",
                vpc_id=None,  # Would need to extract from NIC
                subnet_id=None,
                security_groups=[],
                launch_time=None,
                metadata={
                    "resource_group": resource_group,
                    "vm_id": vm.vm_id,
                }
            )
            discovered_nodes.append(node)

        logger.info(
            "Azure discovery complete",
            total_instances=len(discovered_nodes)
        )

        return discovered_nodes


class GCPInventoryProvider(CloudInventoryProvider):
    """GCP Compute Engine inventory provider."""

    def __init__(
        self,
        project_id: str,
        credentials_json: Optional[str] = None,
        service_account_file: Optional[str] = None,
    ):
        self.project_id = project_id
        self.credentials_json = credentials_json
        self.service_account_file = service_account_file
        self._credentials = None

    def _get_credentials(self):
        """Get GCP credentials."""
        if self._credentials is None:
            from google.oauth2 import service_account
            import json

            if self.credentials_json:
                # Parse JSON string
                info = json.loads(self.credentials_json)
                self._credentials = service_account.Credentials.from_service_account_info(info)
            elif self.service_account_file:
                self._credentials = service_account.Credentials.from_service_account_file(
                    self.service_account_file
                )
            else:
                # Use default credentials (ADC)
                import google.auth
                self._credentials, _ = google.auth.default()

        return self._credentials

    def get_provider_name(self) -> str:
        return "gcp"

    async def validate_credentials(self) -> bool:
        """Validate GCP credentials."""
        try:
            import asyncio
            from googleapiclient.discovery import build

            credentials = self._get_credentials()
            compute = build("compute", "v1", credentials=credentials)

            loop = asyncio.get_event_loop()
            project = await loop.run_in_executor(
                None,
                lambda: compute.projects().get(project=self.project_id).execute()
            )

            logger.info(
                "GCP credentials validated",
                project_id=self.project_id,
                project_name=project.get("name")
            )
            return True
        except Exception as e:
            logger.error("GCP credential validation failed", error=str(e))
            raise CloudCredentialError(f"GCP credential validation failed: {e}")

    async def discover_instances(
        self,
        filters: Optional[Dict[str, Any]] = None,
        regions: Optional[List[str]] = None,
    ) -> List[CloudDiscoveredNode]:
        """Discover GCP Compute instances."""
        import asyncio
        from googleapiclient.discovery import build

        credentials = self._get_credentials()
        compute = build("compute", "v1", credentials=credentials)

        loop = asyncio.get_event_loop()

        # Get all zones (GCP uses zones, not regions for instances)
        zones_response = await loop.run_in_executor(
            None,
            lambda: compute.zones().list(project=self.project_id).execute()
        )

        zones = []
        for zone in zones_response.get("items", []):
            zone_name = zone["name"]
            # Filter by region if specified
            if regions:
                zone_region = "-".join(zone_name.split("-")[:-1])
                if zone_region not in regions:
                    continue
            zones.append(zone_name)

        discovered_nodes = []

        for zone in zones:
            try:
                instances_response = await loop.run_in_executor(
                    None,
                    lambda z=zone: compute.instances().list(
                        project=self.project_id,
                        zone=z
                    ).execute()
                )

                for instance in instances_response.get("items", []):
                    # Filter by labels
                    if filters and "tags" in filters:
                        instance_labels = instance.get("labels", {})
                        match = all(
                            instance_labels.get(k) == v
                            for k, v in filters["tags"].items()
                        )
                        if not match:
                            continue

                    node = self._instance_to_node(instance, zone)
                    if node:
                        discovered_nodes.append(node)

            except Exception as e:
                logger.warning(
                    "Failed to discover instances in zone",
                    zone=zone,
                    error=str(e)
                )

        logger.info(
            "GCP discovery complete",
            total_instances=len(discovered_nodes),
            zones_scanned=len(zones)
        )

        return discovered_nodes

    def _instance_to_node(self, instance: Dict, zone: str) -> Optional[CloudDiscoveredNode]:
        """Convert GCP instance to CloudDiscoveredNode."""
        instance_id = str(instance.get("id"))
        name = instance.get("name", instance_id)

        # Get IPs from network interfaces
        private_ip = None
        public_ip = None

        for nic in instance.get("networkInterfaces", []):
            private_ip = nic.get("networkIP")
            for access_config in nic.get("accessConfigs", []):
                public_ip = access_config.get("natIP")
                break
            break

        # Determine platform from disk
        platform = "linux"
        for disk in instance.get("disks", []):
            licenses = disk.get("licenses", [])
            for lic in licenses:
                if "windows" in lic.lower():
                    platform = "windows"
                    break

        # Get region from zone
        region = "-".join(zone.split("-")[:-1])

        # Get machine type (last part of URL)
        machine_type_url = instance.get("machineType", "")
        machine_type = machine_type_url.split("/")[-1] if machine_type_url else "unknown"

        return CloudDiscoveredNode(
            instance_id=instance_id,
            name=name,
            private_ip=private_ip,
            public_ip=public_ip,
            platform=platform,
            instance_type=machine_type,
            region=region,
            zone=zone,
            state=instance.get("status", "").lower(),
            tags=instance.get("labels", {}),
            labels={},
            cloud_provider="gcp",
            vpc_id=None,
            subnet_id=None,
            security_groups=[],
            launch_time=None,
            metadata={
                "self_link": instance.get("selfLink"),
                "creation_timestamp": instance.get("creationTimestamp"),
            }
        )


class CloudInventoryService:
    """
    Main service for cloud inventory operations.

    Provides a unified interface for discovering nodes from
    multiple cloud providers.
    """

    def __init__(self):
        self._providers: Dict[str, CloudInventoryProvider] = {}

    def register_provider(
        self,
        provider_name: str,
        provider: CloudInventoryProvider
    ) -> None:
        """Register a cloud provider."""
        self._providers[provider_name] = provider
        logger.info(
            "Cloud provider registered",
            provider=provider_name
        )

    def get_provider(self, provider_name: str) -> Optional[CloudInventoryProvider]:
        """Get a registered provider."""
        return self._providers.get(provider_name)

    async def discover_from_provider(
        self,
        provider_name: str,
        filters: Optional[Dict[str, Any]] = None,
        regions: Optional[List[str]] = None,
    ) -> List[CloudDiscoveredNode]:
        """Discover instances from a specific provider."""
        provider = self._providers.get(provider_name)
        if not provider:
            raise CloudProviderError(f"Provider {provider_name} not registered")

        return await provider.discover_instances(filters=filters, regions=regions)

    async def discover_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        regions: Optional[List[str]] = None,
    ) -> Dict[str, List[CloudDiscoveredNode]]:
        """Discover instances from all registered providers."""
        results = {}

        for name, provider in self._providers.items():
            try:
                nodes = await provider.discover_instances(
                    filters=filters,
                    regions=regions
                )
                results[name] = nodes
            except Exception as e:
                logger.error(
                    "Discovery failed for provider",
                    provider=name,
                    error=str(e)
                )
                results[name] = []

        return results

    async def validate_all_credentials(self) -> Dict[str, bool]:
        """Validate credentials for all registered providers."""
        results = {}

        for name, provider in self._providers.items():
            try:
                results[name] = await provider.validate_credentials()
            except CloudCredentialError:
                results[name] = False

        return results


# Factory functions for creating providers
def create_aws_provider(
    access_key_id: Optional[str] = None,
    secret_access_key: Optional[str] = None,
    region: str = "us-east-1",
    assume_role_arn: Optional[str] = None,
    profile_name: Optional[str] = None,
) -> AWSInventoryProvider:
    """Create an AWS inventory provider."""
    return AWSInventoryProvider(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        region=region,
        assume_role_arn=assume_role_arn,
        profile_name=profile_name,
    )


def create_azure_provider(
    subscription_id: str,
    tenant_id: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    use_managed_identity: bool = False,
) -> AzureInventoryProvider:
    """Create an Azure inventory provider."""
    return AzureInventoryProvider(
        subscription_id=subscription_id,
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        use_managed_identity=use_managed_identity,
    )


def create_gcp_provider(
    project_id: str,
    credentials_json: Optional[str] = None,
    service_account_file: Optional[str] = None,
) -> GCPInventoryProvider:
    """Create a GCP inventory provider."""
    return GCPInventoryProvider(
        project_id=project_id,
        credentials_json=credentials_json,
        service_account_file=service_account_file,
    )
