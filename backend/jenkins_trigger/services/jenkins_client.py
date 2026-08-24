"""
Jenkins API client.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote

import requests

@dataclass
class JenkinsParamDefinition:
    """Jenkins parameter definition."""

    name: str
    type: str
    default_value: Optional[str] = None
    choices: Optional[list] = None
    description: Optional[str] = None


@dataclass
class JenkinsBuildParamValue:
    """Resolved Jenkins build parameter value."""

    value: str
    source: str


@dataclass
class JenkinsBuildResult:
    """Jenkins build result."""

    build_number: int
    result: Optional[str]
    duration: int
    timestamp: int
    artifacts: list


@dataclass
class JenkinsPipelineProgress:
    """Pipeline stage progress parsed from Jenkins workflow API."""

    pipeline_supported: bool
    progress_percent: Optional[int] = None
    current_stage: str = ""
    stage_summary: Optional[dict[str, int]] = None
    stages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class JenkinsBuildTriggerResult:
    """Result returned immediately after Jenkins accepts a build trigger."""

    queue_url: str = ""
    queue_id: Optional[int] = None
    build_number: Optional[int] = None


@dataclass
class JenkinsQueueItem:
    """Jenkins queue item state."""

    queue_id: Optional[int] = None
    executable_number: Optional[int] = None
    executable_url: str = ""
    cancelled: bool = False
    why: str = ""


@dataclass
class JenkinsJobNode:
    """Jenkins job tree node."""

    full_name: str
    display_name: str
    url: str
    type: str
    has_children: bool
    buildable: Optional[bool] = None
    color: str = ""
    children: list["JenkinsJobNode"] = field(default_factory=list)


class JenkinsClient:
    """Jenkins REST API client."""

    def __init__(self, url: str, username: str, token: str):
        self.url = url.rstrip("/")
        self.auth = (username, token)
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.auth = self.auth
        self.crumb = None

    def _build_job_api_url(self, job_name: Optional[str] = None) -> str:
        """Build a Jenkins API URL for a root or nested job."""
        if not job_name:
            return f"{self.url}/api/json"

        job_path = "/".join(f"job/{quote(part, safe='')}" for part in job_name.split("/") if part)
        return f"{self.url}/{job_path}/api/json"

    def _build_job_path(self, job_name: str, action: str) -> str:
        """Build a Jenkins job action path that supports folders."""
        job_path = "/".join(f"job/{quote(part, safe='')}" for part in job_name.split("/") if part)
        return f"{self.url}/{job_path}/{action}"

    def _absolute_jenkins_url(self, url: str) -> str:
        """Normalize a Jenkins URL returned by Jenkins itself."""
        if not url:
            return ""
        if url.startswith("/"):
            return f"{self.url}{url}"
        return url

    @staticmethod
    def _parse_queue_id(location: str) -> Optional[int]:
        parts = location.rstrip("/").split("/")
        for index, part in enumerate(parts[:-2]):
            if part == "queue" and parts[index + 1] == "item":
                try:
                    return int(parts[index + 2])
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _parse_build_number(location: str) -> Optional[int]:
        if JenkinsClient._parse_queue_id(location) is not None:
            return None
        try:
            return int(location.rstrip("/").split("/")[-1])
        except (TypeError, ValueError, IndexError):
            return None

    def _is_container_job(self, item: dict[str, Any]) -> bool:
        """Return whether the Jenkins item can contain child jobs."""
        job_class = (item.get("_class") or "").lower()
        if "folder" in job_class:
            return True
        if "multibranch" in job_class:
            return True
        if "organization" in job_class:
            return True
        return bool(item.get("jobs"))

    def _get_crumb(self) -> str:
        """Get Jenkins CSRF crumb."""
        if self.crumb:
            return self.crumb

        response = self.session.get(
            f"{self.url}/crumbIssuer/api/json",
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self.crumb = data.get("crumbRequestField", "Jenkins-Crumb")
        self.crumb_value = data.get("crumb")
        return self.crumb_value

    def _fetch_job_children(self, job_name: Optional[str] = None) -> list[JenkinsJobNode]:
        """Fetch direct children for a Jenkins root or folder/job node."""
        response = self.session.get(
            self._build_job_api_url(job_name),
            params={
                "tree": "jobs[fullName,displayName,name,url,_class,buildable,color]"
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        nodes: list[JenkinsJobNode] = []
        for item in data.get("jobs", []):
            full_name = item.get("fullName") or item.get("full_name") or item.get("name", "")
            display_name = item.get("displayName") or item.get("display_name") or item.get("name", full_name)
            is_container = self._is_container_job(item)
            children = self._fetch_job_children(full_name) if is_container else []
            node_type = "folder" if is_container else "job"

            nodes.append(
                JenkinsJobNode(
                    full_name=full_name,
                    display_name=display_name,
                    url=item.get("url") or "",
                    type=node_type,
                    has_children=bool(children),
                    buildable=item.get("buildable"),
                    color=item.get("color") or "",
                    children=children,
                )
            )

        return nodes

    def _headers(self) -> dict:
        """Get headers with CSRF crumb."""
        crumb_value = self._get_crumb()
        return {
            "Jenkins-Crumb": crumb_value,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def test_connection(self) -> tuple[bool, str]:
        """Test Jenkins connection.

        Returns a tuple of (success, message) so callers can surface the real
        reason when connectivity or authentication fails.
        """
        try:
            response = self.session.get(
                f"{self.url}/api/json",
                timeout=30,
            )

            if response.ok:
                return True, "连接成功"

            if response.status_code in (401, 403):
                try:
                    anonymous_session = requests.Session()
                    anonymous_session.trust_env = False
                    anonymous_response = anonymous_session.get(
                        f"{self.url}/api/json",
                        timeout=30,
                    )
                    if anonymous_response.ok:
                        return False, "Jenkins 可访问，但认证失败，请检查用户名或 API Token"
                except requests.RequestException:
                    # If the anonymous probe also fails, fall through to the
                    # authenticated error so callers still get the HTTP status.
                    pass

                return False, f"认证失败（HTTP {response.status_code} {response.reason}），请检查用户名或 API Token"

            return False, f"Jenkins 返回 HTTP {response.status_code} {response.reason}"
        except requests.exceptions.Timeout:
            return False, "连接 Jenkins 超时，请检查地址和网络"
        except requests.exceptions.ConnectionError:
            return False, "无法连接到 Jenkins，请检查地址和网络"
        except requests.exceptions.RequestException:
            return False, "Jenkins 请求失败，请稍后重试"
        except Exception:
            return False, "Jenkins 连接测试失败，请检查实例配置"

    def get_job_params(self, job_name: str) -> list[JenkinsParamDefinition]:
        """
        Get parameter definitions for a job.

        Jenkins parameterDefinitions may appear under property or actions,
        depending on the job type and Jenkins/plugins in use.
        """
        try:
            response = self.session.get(
                self._build_job_api_url(job_name),
                params={
                    "tree": (
                        "property[parameterDefinitions[name,type,defaultValue,"
                        "defaultParameterValue[value],choices,description]],"
                        "actions[parameterDefinitions[name,type,defaultValue,"
                        "defaultParameterValue[value],choices,description]]"
                    )
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            params = []
            seen_names = set()

            containers = []
            containers.extend(data.get("property", []))
            containers.extend(data.get("actions", []))

            for container in containers:
                param_defs = container.get("parameterDefinitions", [])
                for param in param_defs:
                    name = param.get("name", "")
                    if not name or name in seen_names:
                        continue
                    seen_names.add(name)

                    params.append(
                        JenkinsParamDefinition(
                            name=name,
                            type=param.get("type", "StringParameterDefinition"),
                            default_value=(
                                param.get("defaultParameterValue", {}).get("value")
                                if isinstance(param.get("defaultParameterValue"), dict)
                                else param.get("defaultValue")
                            ),
                            choices=param.get("choices"),
                            description=param.get("description"),
                        )
                    )
            return params
        except Exception:
            raise

    def get_last_successful_build_params(self, job_name: str) -> dict[str, str]:
        """Get parameters from the last successful Jenkins build."""
        try:
            response = self.session.get(
                self._build_job_api_url(job_name),
                params={
                    "tree": (
                        "lastSuccessfulBuild[number,"
                        "actions[_class,parameters[name,value]]]"
                    )
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            raise

        last_successful_build = data.get("lastSuccessfulBuild") or {}
        if not last_successful_build:
            return {}

        params: dict[str, str] = {}
        for action in last_successful_build.get("actions", []):
            action_class = (action.get("_class") or "").lower()
            if "parametersaction" not in action_class:
                continue

            for param in action.get("parameters", []):
                name = param.get("name")
                if not name:
                    continue
                value = param.get("value")
                params[name] = "" if value is None else str(value)

        return params

    def trigger_build(
        self,
        job_name: str,
        params: Optional[dict[str, str]] = None,
    ) -> JenkinsBuildTriggerResult:
        """
        Trigger a Jenkins build with parameters.

        Jenkins usually returns a queue item URL, not the final build URL.
        """
        try:
            if params:
                # Build with parameters
                url = self._build_job_path(job_name, "buildWithParameters")
                data = params
            else:
                # Build without parameters
                url = self._build_job_path(job_name, "build")
                data = {}

            response = self.session.post(
                url,
                data=data,
                headers=self._headers(),
                timeout=60,
                allow_redirects=False,
            )

            if response.status_code in {200, 201, 202, 302, 303, 307, 308}:
                location = response.headers.get("Location", "")
                if not location:
                    raise Exception(
                        f"Jenkins returned HTTP {response.status_code} but did not provide queue/build location"
                    )

                normalized_location = self._absolute_jenkins_url(location)
                queue_id = self._parse_queue_id(normalized_location)
                build_number = self._parse_build_number(normalized_location)
                return JenkinsBuildTriggerResult(
                    queue_url=normalized_location if queue_id is not None else "",
                    queue_id=queue_id,
                    build_number=build_number,
                )
            raise Exception(f"Failed to trigger build: {response.status_code}")

        except Exception:
            raise

    def get_queue_item(self, queue_url: str) -> JenkinsQueueItem:
        """Get Jenkins queue item state from a queue URL."""
        try:
            normalized_url = self._absolute_jenkins_url(queue_url).rstrip("/")
            response = self.session.get(
                f"{normalized_url}/api/json",
                params={"tree": "id,cancelled,why,executable[number,url]"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            executable = data.get("executable") or {}
            executable_number = executable.get("number")
            return JenkinsQueueItem(
                queue_id=data.get("id") or self._parse_queue_id(normalized_url),
                executable_number=executable_number if executable_number is None else int(executable_number),
                executable_url=executable.get("url") or "",
                cancelled=bool(data.get("cancelled")),
                why=data.get("why") or "",
            )
        except Exception:
            raise

    def get_queue_item_by_id(self, queue_id: int) -> JenkinsQueueItem:
        """Get Jenkins queue item state by queue id."""
        return self.get_queue_item(f"{self.url}/queue/item/{queue_id}/")

    def find_build_number_by_queue_id(self, job_name: str, queue_id: int) -> Optional[int]:
        """Find a build number by Jenkins queue id when the queue item has expired."""
        try:
            response = self.session.get(
                self._build_job_api_url(job_name),
                params={
                    "tree": "builds[number,queueId,url]"
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            for build in data.get("builds", []):
                if build.get("queueId") == queue_id:
                    build_number = build.get("number")
                    return None if build_number is None else int(build_number)
            return None
        except Exception:
            raise

    def get_build_result(self, job_name: str, build_number: int) -> JenkinsBuildResult:
        """
        Get build result.
        """
        try:
            response = self.session.get(
                self._build_job_path(job_name, f"{build_number}/api/json"),
                params={"tree": "result,duration,timestamp,number,artifacts[relativePath,fileName]"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            return JenkinsBuildResult(
                build_number=data.get("number", build_number),
                result=data.get("result"),
                duration=data.get("duration", 0),
                timestamp=data.get("timestamp", 0),
                artifacts=data.get("artifacts", []),
            )
        except Exception:
            raise

    def get_pipeline_progress(
        self,
        job_name: str,
        build_number: int,
    ) -> JenkinsPipelineProgress:
        """Get Pipeline stage progress from Jenkins workflow API."""
        try:
            response = self.session.get(
                self._build_job_path(job_name, f"{build_number}/wfapi/describe"),
                timeout=30,
            )
            if response.status_code == 404:
                return JenkinsPipelineProgress(pipeline_supported=False)
            response.raise_for_status()
            data = response.json()
        except Exception:
            raise

        stages = data.get("stages") or []
        if not isinstance(stages, list) or not stages:
            return JenkinsPipelineProgress(pipeline_supported=False)

        completed_statuses = {"SUCCESS", "FAILED", "FAILURE", "ABORTED"}
        skipped_statuses = {"NOT_EXECUTED"}
        normalized_stages = []
        completed_count = 0
        current_stage = ""

        for stage in stages:
            if not isinstance(stage, dict):
                continue
            name = stage.get("name") or ""
            status = (stage.get("status") or "").upper()
            normalized_stages.append(
                {
                    "id": stage.get("id"),
                    "name": name,
                    "status": status,
                    "duration_millis": stage.get("durationMillis") or 0,
                }
            )
            if status in completed_statuses:
                completed_count += 1
            elif status not in skipped_statuses and not current_stage:
                current_stage = name

        total_count = len(normalized_stages)
        if total_count == 0:
            return JenkinsPipelineProgress(pipeline_supported=False)

        progress_percent = int(round((completed_count / total_count) * 100))
        progress_percent = max(0, min(progress_percent, 100))

        return JenkinsPipelineProgress(
            pipeline_supported=True,
            progress_percent=progress_percent,
            current_stage=current_stage,
            stage_summary={
                "total": total_count,
                "completed": completed_count,
            },
            stages=normalized_stages,
        )

    def get_build_console(self, job_name: str, build_number: int) -> str:
        """
        Get build console output.
        """
        try:
            response = self.session.get(
                self._build_job_path(job_name, f"{build_number}/consoleText"),
                timeout=60,
            )
            response.raise_for_status()
            return response.text
        except Exception:
            raise

    def list_jobs(self) -> list[JenkinsJobNode]:
        """List Jenkins jobs recursively."""
        try:
            return self._fetch_job_children(None)
        except Exception:
            raise
