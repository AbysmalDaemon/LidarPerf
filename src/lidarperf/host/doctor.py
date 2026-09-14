"""Read-only benchmark-host readiness assessment."""

from __future__ import annotations

from .models import DoctorIssue, DoctorReport, DoctorSeverity, HostSnapshot


def _issue(
    severity: DoctorSeverity,
    code: str,
    message: str,
    *,
    blocks_controlled: bool = False,
) -> DoctorIssue:
    return DoctorIssue(
        severity=severity,
        code=code,
        message=message,
        blocks_controlled=blocks_controlled,
    )


def assess_host(snapshot: HostSnapshot) -> DoctorReport:
    """Assess whether a snapshot is suitable for exploratory or controlled measurements."""

    issues: list[DoctorIssue] = []
    is_linux = snapshot.os.system.lower() == "linux"
    if not is_linux:
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "NON_LINUX_HOST",
                "Controlled process benchmarking is Linux-only in LidarPerf v0.1.",
                blocks_controlled=True,
            )
        )

    if not snapshot.cpu.affinity_cpus:
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "CPU_AFFINITY_UNKNOWN",
                "CPU affinity could not be inspected; controlled CPU allocation cannot be proven.",
                blocks_controlled=True,
            )
        )
    elif snapshot.cpu.affinity_count == snapshot.cpu.logical_cpus:
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "CPU_AFFINITY_UNRESTRICTED",
                "The process can use every logical CPU; controlled runs should pin "
                "an explicit CPU set.",
            )
        )

    governors = {value.lower() for value in snapshot.cpu.governors}
    if "powersave" in governors:
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "CPU_GOVERNOR_POWERSAVE",
                "At least one CPU policy reports the powersave governor; record/stabilize "
                "frequency policy.",
            )
        )
    elif not snapshot.cpu.governors and is_linux:
        issues.append(
            _issue(
                DoctorSeverity.INFO,
                "CPU_GOVERNOR_UNKNOWN",
                "CPU scaling governor information is unavailable on this host.",
            )
        )

    if is_linux and snapshot.cgroups.version == "none":
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "CGROUPS_UNAVAILABLE",
                "Linux cgroups are unavailable; benchmark-grade process accounting "
                "cannot be established.",
                blocks_controlled=True,
            )
        )
    elif is_linux and snapshot.cgroups.version == "unknown":
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "CGROUPS_UNKNOWN",
                "The cgroup layout could not be classified.",
                blocks_controlled=True,
            )
        )
    elif is_linux and snapshot.cgroups.writable is False:
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "CGROUPS_NOT_WRITABLE",
                "The visible cgroup root is not directly writable; BenchExec delegation "
                "must be verified.",
            )
        )

    if not snapshot.runtime.runexec_available and not snapshot.runtime.benchexec_available:
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "BENCHEXEC_UNAVAILABLE",
                "BenchExec/runexec is not available; controlled process metrics require "
                "it in v0.1.",
                blocks_controlled=True,
            )
        )

    swap_used = snapshot.memory.swap_used_bytes
    if swap_used is not None and swap_used > 0:
        issues.append(
            _issue(
                DoctorSeverity.WARNING,
                "SWAP_IN_USE",
                f"Swap is currently in use ({swap_used} bytes); this can perturb latency "
                "measurements.",
            )
        )

    if snapshot.runtime.load_1m is not None and snapshot.cpu.affinity_count:
        normalized_load = snapshot.runtime.load_1m / snapshot.cpu.affinity_count
        if normalized_load > 0.5:
            issues.append(
                _issue(
                    DoctorSeverity.WARNING,
                    "ELEVATED_SYSTEM_LOAD",
                    "One-minute system load exceeds 0.5 per CPU available to this process.",
                )
            )

    if snapshot.storage.inspected:
        if snapshot.storage.exists is False:
            issues.append(
                _issue(
                    DoctorSeverity.ERROR,
                    "DATA_PATH_MISSING",
                    "The requested benchmark data path does not exist.",
                )
            )
        elif snapshot.storage.network_filesystem is True:
            issues.append(
                _issue(
                    DoctorSeverity.WARNING,
                    "NETWORK_FILESYSTEM",
                    "The benchmark data path is on a network filesystem; end-to-end I/O "
                    "may be noisy.",
                )
            )
        elif snapshot.storage.filesystem_type is None:
            issues.append(
                _issue(
                    DoctorSeverity.INFO,
                    "FILESYSTEM_TYPE_UNKNOWN",
                    "The benchmark data path filesystem type could not be identified.",
                )
            )

    if snapshot.cpu.thermal_throttle_count is not None and snapshot.cpu.thermal_throttle_count > 0:
        issues.append(
            _issue(
                DoctorSeverity.INFO,
                "THERMAL_THROTTLE_HISTORY",
                "CPU thermal-throttle counters are nonzero; these counters may include "
                "earlier activity.",
            )
        )

    blockers = any(issue.blocks_controlled for issue in issues)
    classes: tuple[str, ...]
    if blockers:
        classes = ("exploratory",)
    else:
        classes = ("exploratory", "controlled")
    return DoctorReport(
        snapshot=snapshot,
        eligible_measurement_classes=classes,
        issues=tuple(issues),
    )
