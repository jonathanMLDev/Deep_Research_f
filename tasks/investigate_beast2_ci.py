"""
Beast2 CI Availability Improvement Options Investigation

This task researches options for improving CI availability and speed for Beast2,
including GitHub Enterprise plans, dedicated runners, CI optimization, and
cloud vs. hardware infrastructure options.

Usage:
    python -m tasks.investigate_beast2_ci
"""

from deep_research.main_process import execute_main_process

OUTPUT_PATH = "report_for_beast2_ci"


def create_research_query() -> str:
    return """Generate a comprehensive report on Beast2 CI Availability Improvement Options addressing the following:

**Current CI Configuration (from ci.yml):**
- Matrix strategy with ~50+ build configurations (Windows MSVC, Clang, MinGW; macOS Apple-Clang; Linux GCC, Clang)
- Multiple compiler versions (GCC 11-15, Clang 10-20, MSVC 14.34-14.42, etc.)
- Multiple C++ standards (C++17, C++20, C++23)
- Multiple build types (Release, Debug, RelWithDebInfo)
- Multiple platforms (Windows 2022, macOS 14-26, Ubuntu 20.04-25.04)
- Additional jobs: changelog, antora docs (3 OS variants)
- Uses GitHub-hosted runners by default (ubuntu-latest, windows-2022, macos-*)
- Has AWS-hosted runner support for boostorg organization
- Strategy: fail-fast: false (allows parallel execution)

**Current Problems:**
- Each job takes 2-3 minutes to execute, but we want to run them in parallel to reduce total runtime
- Queue wait times: Worst-case scenario is 2 hours; typical waits vary but can be significant during peak usage
- With ~50+ matrix jobs, sequential execution would take hours; parallel execution is critical
- Inconsistent job completion: Sometimes individual jobs take 8 minutes while others finish in 2 minutes, causing total workflow time to be determined by slowest job
- 2-5 minute total CI time is still considered long; need faster plan focusing on min/max times, especially optimizing max time

**Report Structure:**

Executive Summary
   - Summary of the report
   - Key findings and recommendations
   - Cost-benefit analysis
   - Runtime reduction estimates
   - Queue wait time elimination strategies
   - Comparison of GitHub-hosted runners, self-hosted runners (AWS/GCP/Azure), and third-party SaaS runner providers (RunsOn, Ubicloud, Buildjet, Namespace, Cirrus, ARC, etc.)
   - Reference performance benchmarks from runs-on.com for CPU and I/O performance comparisons where applicable
   - Analysis of open source runner alternatives: Document findings from investigating open source GitHub Actions runner solutions (like actions-runner-controller, act, and other implementations), their capabilities, setup requirements, cost structure, and how they compare to commercial third-party providers

1. GitHub Organization Plan Analysis
   - Cost comparison by plan (current pricing, annual vs. monthly, per-user costs)
   - Add action compare table by plan: Reference "Free use of GitHub Actions" table from https://docs.github.com/en/billing/concepts/product-billing/github-actions showing included minutes, pricing for additional minutes by plan (Free, Pro,Team, Enterprise)
   - Benefits of most suitable plan for our use case:
     * Dedicated runners to eliminate queue wait times (worst case: 2 hours)
     * Parallel job execution capabilities
     * Repository-level runner assignment (Beast2, Http.Io, Buffers, Capy - select repositories only)
     * Advanced security and compliance features
   - Explore dedicated runners for the team (Beast2, Http.Io, Buffers, Capy - select repositories only)
     * Setup requirements and configuration
     * Cost implications for dedicated runners
     * Repository-level runner assignment capabilities
     * Performance benefits vs. GitHub-hosted runners
     * Impact on queue wait times (target: eliminate worst-case 2-hour waits)
     * Check if there is an option in GitHub self-hosted runner settings that custom daily time range is possible (e.g., full coverage during 8AM-8PM PT, reduced/no coverage during other times)
   - Parallel job execution:
     * Maximum concurrent jobs supported (need to run ~50+ matrix jobs in parallel)
     * Cost implications of parallel execution (50+ concurrent jobs)
     * How parallel execution affects total CI runtime (from hours to minutes)
     * Current GitHub-hosted runner limits vs. Enterprise/dedicated runner limits
     * Impact on queue wait times with dedicated runners

2. CI Speed Optimization Report
   - Open Source GitHub Actions Runner Alternatives Research:
     * Investigate open source alternatives to GitHub Actions runners (not C++ libraries, but runner solutions themselves)
     * Research open source implementations and tools for self-hosted GitHub Actions runners
     * Examples to investigate:
       - actions-runner-controller (ARC) - Kubernetes-based open source solution
       - act - Local GitHub Actions runner for testing
       - Other open source GitHub Actions runner implementations
       - Open source CI/CD platforms that integrate with GitHub Actions
       - Self-hosted runner management tools and frameworks
       - Open source solutions for runner orchestration and scaling
     * Analyze their capabilities:
       - How they implement GitHub Actions runner protocol
       - Support for Linux, Windows, macOS runners
       - Scaling and autoscaling capabilities
       - Cost structure (open source = no licensing fees, only infrastructure)
       - Integration with cloud providers (AWS, GCP, Azure)
       - Queue management and concurrency handling
       - Caching support and strategies
       - Security and isolation features
     * Compare open source solutions vs commercial third-party providers:
       - Setup complexity and maintenance overhead
       - Feature completeness vs commercial alternatives
       - Community support and documentation
       - Customization and extensibility
       - Total cost of ownership (infrastructure only vs infrastructure + licensing)
     * Identify best practices from open source runner implementations
     * Document successful open source runner deployments and configurations
     * Evaluate which open source solutions would work best for Beast2's use case (GCP infrastructure, multi-platform needs)
   - Current CI Statistics and Baseline:
     * Gather statistics from https://github.com/cppalliance/beast2/actions and https://github.com/cppalliance/capy/actions for the past week
     * Number of action runs, min/max/average/median time for each action run
     * These stats provide rough estimate for upcoming workflow and are expected to increase in the short future
   - How fast can the current CI process be made to go (excluding slop-driven development)
     * Current CI pipeline bottlenecks:
       - ~50+ matrix jobs × 2-3 min each = 100-150 minutes if sequential
       - Queue wait times: Worst-case scenario is 2 hours; typical waits vary
       - Total CI cycle time: hours (queue + execution)
       - Inconsistent job completion: Sometimes individual jobs take 8 minutes while others finish in 2 minutes
     * Performance targets:
       - 2-5 minute total CI time is still considered long for rapid AI bot iteration
       - Need faster plan focusing on min/max times, especially optimizing max time
       - Target: Sub-2 minute median, with max times under 3 minutes
       - Eliminate straggler jobs that take 8 minutes while others finish in 2 minutes
     * Parallelization strategies for ~50+ jobs:
       - Running all matrix jobs simultaneously
       - Reducing total CI time from hours to sub-2 minutes (parallel execution)
       - Ensure consistent job resource allocation to prevent stragglers
     * Caching and dependency management improvements:
       - GitHub Actions cache: What is GitHub cache action? Can it be the lowest hanging fruit?
       - GitHub supports more than 10GB cache size on pay-as-you-go model (source: https://github.blog/changelog/2025-11-20-github-actions-cache-size-can-now-exceed-10-gb-per-repository/)
       - What is the cache size limit on our current subscription tier (Free/Team/Enterprise)?
       - Cache management policies: cache size eviction limit (GB) and cache retention limit (days)
       - Boost source caching (already using boost-clone action)
       - Dependency caching (zlib, openssl, brotli) using GitHub cache action
       - Build artifact caching
       - Compiler caches (ccache/sccache)
     * Expected runtime reduction:
       - Current: Hours (queue + sequential execution)
       - With parallel execution: Sub-2 minutes (all jobs run simultaneously)
       - With dedicated runners: Eliminate queue waits entirely
       - Focus on reducing max workflow duration, not just average
   - Cost analysis with 3 pricing tiers:
     * Most expensive option: High-performance dedicated runners with premium hardware
       - Expected runtime reduction
       - Queue elimination capabilities
       - Parallel job capacity
     * Mid-tier option: Balanced performance and cost
       - Expected runtime reduction
       - Queue wait time reduction
       - Parallel job capacity
     * Low-tier option: Cost-effective solution with acceptable performance
       - Expected runtime reduction
       - Queue wait time reduction
       - Parallel job capacity
   - Include high-performance hardware specs (e.g., Xeon with many processors, large memory)
     * CPU specifications (cores, threads, clock speed) for parallel job execution
     * Memory requirements (RAM capacity) for multiple concurrent jobs
     * Storage options (SSD, NVMe) for fast build times
     * Network capabilities for artifact transfer
   - Scope: dedicated runners for the team only (Beast2, Http.Io, Buffers, Capy repositories)
   - Confirm if the same runners can also support cloud-based slop-driven development
     * Compatibility with cloud CI/CD workflows
     * Multi-repository support capabilities
     * Resource sharing and isolation
     * Ability to handle both automated bot-driven CI and manual development workflows

3. Cloud vs. Hardware Infrastructure Report
   - Options for cloud services (AWS, GCP, Azure) that can provide fast dedicated slots
     * Compare AWS vs GCP vs Azure pricing: We are currently relying heavily on Google Cloud, but if we can save much $$$, we're open to migrating to other platforms
     * AWS EC2 instances (compute-optimized, memory-optimized) for CI runners
     * Google Cloud Platform (GCP) Compute Engine instances (N2, C2 families) - current infrastructure
     * Azure Virtual Machines (Dv5, Dsv5, Fsv5, Fsv2 series)
     * AWS CodeBuild, Google Cloud Build, Azure Pipelines
     * Dedicated instance options and pricing comparison across all three providers
     * Queue elimination and parallel execution capabilities
     * Integration with GitHub Actions
     * Migration considerations and cost-benefit analysis
   - Third-party runner service alternatives (reference: https://runs-on.com/alternatives-to/github-actions-runners/):
     * Overview of major alternatives: RunsOn, Buildjet, Ubicloud, Blacksmith, Namespace, Depot, Warpbuild, Cirrus, actions-runner-controller (ARC)
     * Compare third-party SaaS runner providers vs self-hosted runners vs GitHub-hosted runners
     * Cost comparison: Which providers offer 90% cost reduction vs GitHub-hosted runners?
       - RunsOn: Small yearly license (from €300), compute billed directly by AWS, can use AWS credits
       - Ubicloud: Hetzner-based, 90% cheaper than GitHub-hosted
       - Other providers: Per-minute pricing models
     * Performance comparison: CPU benchmarks, I/O benchmarks, queue times (reference runs-on.com benchmarks)
       - Fastest x64: Namespace, Cirrus
       - Best arm64 price/performance: RunsOn
       - Queue times: Most alternatives maintain competitive queue times (typically under 30 seconds)
     * Security trade-offs:
       - Third-party SaaS: Code runs on their infrastructure (Buildjet, Ubicloud, Namespace, etc.)
       - Self-hosted solutions: Code stays in your VPC (RunsOn deploys in your AWS, ARC in your Kubernetes)
     * Platform-specific considerations:
       - RunsOn: AWS-only, deploys in your AWS account, can use AWS credits, yearly license from €300
       - Ubicloud: Hetzner-based, 90% cheaper, good for cost optimization
       - ARC (actions-runner-controller): Kubernetes-based, works with any cloud provider including GCP
     * Feature support:
       - macOS: Multiple providers offer macOS, but AWS-based solutions face 24-hour reservation limitations
       - Windows: RunsOn and some open-source solutions support Windows
       - GPU: RunsOn offers GPU support
       - Instance types: Some providers support up to 896 vCPUs
       - Unlimited concurrency policies
     * Best fit analysis for Beast2:
       - If staying on GCP: Consider ARC (Kubernetes-based) or evaluate GCP-native solutions
       - If open to AWS: RunsOn offers self-hosted deployment in your AWS, use AWS credits
       - If cost is primary concern: Ubicloud (Hetzner-based) offers 90% savings
       - If performance is critical: Namespace or Cirrus for fastest x64 performance
       - Best for enterprise: RunsOn (deploys in your AWS), ARC (Kubernetes-based)
     * When to use third-party alternatives vs self-hosted:
       - Third-party: Zero setup, plug-and-play, code runs on their infrastructure
       - Self-hosted: Full control, code stays in your VPC, use existing cloud credits
     * Integration complexity: Third-party SaaS (plug-and-play) vs self-hosted (10+ minutes setup)
     * Integration with existing infrastructure (we currently use GCP heavily)
   - Compare cloud vs. buying own hardware (supercomputer)
     * Initial investment vs. ongoing costs
     * Maintenance and operational overhead
     * Scalability and flexibility for varying CI loads
     * Performance characteristics (queue times, parallel execution)
     * Suitability for automated bot-driven CI cycles
     * Mac builds require M-series CPUs, so a dedicated Apple computer may also be needed
     * Hardware requirements: Linux/Windows servers + M-series Mac for macOS builds
     * Cost comparison including Mac hardware (M-series Mac mini/Studio)
   - Cost comparison (prefers cloud, but depends on price)
     * Total cost of ownership (TCO) analysis across AWS, GCP, Azure
     * Break-even point calculations
     * Long-term cost projections (1-year, 3-year, 5-year)
     * Include hardware depreciation, maintenance, power, cooling, space costs
     * Cost per CI cycle (considering parallel execution and queue elimination)
     * Cost-effectiveness for rapid iteration (AI fixes → CI test → repeat)
     * Migration cost analysis if switching from GCP to AWS/Azure
4. Recommended Options Summary
   - Summary of the CI speed optimization options combined with the best options for our use case

Reference Sources:
  - list of reference sources for the report with corresponding citations [N]


**Key Requirements:**
- Solutions must support rapid iteration cycles (AI bot fixes → CI test → repeat)
- Must eliminate or significantly reduce worst-case 2-hour queue wait times (note: 2-hour queue is worst-case scenario, not typical)
- Must enable parallel execution of multiple jobs (currently 2-3 min each, want to run in parallel)
- Focus on optimizing max workflow duration, not just average (sometimes workflows take 8+ minutes when one job takes 8 minutes while others finish in 2 minutes)
- 2-5 minute total CI time is still considered long; need faster plan with sub-2 minute median and max times under 3 minutes
- Focus on solutions that work with GitHub Actions and automated workflows
- Focus on public repositories (which have unlimited Actions minutes); avoid detailed discussion of private repository pricing/limitations
- Research open source GitHub Actions runner alternatives: Investigate open source solutions for self-hosted runners (like actions-runner-controller, act, and other open source runner implementations) before making recommendations

Provide a CONCISE, OBJECTIVE, and QUANTITATIVE report with:
- Specific pricing information and cost breakdowns
- Technical specifications with concrete numbers
- Comparison tables for easy decision-making (include third-party runner alternatives)
- Short paragraphs (2-4 sentences max)
- Bullet points and tables for better readability
- Clear citations and sources for all pricing and technical data
- Focus on actionable recommendations with cost-benefit analysis
- Runtime reduction estimates (current vs. optimized)
- Queue wait time elimination strategies
- Include comprehensive comparison of: GitHub-hosted runners, self-hosted runners (AWS/GCP/Azure), and third-party SaaS runner providers (RunsOn, Ubicloud, Buildjet, Namespace, Cirrus, ARC, etc.)
- Reference performance benchmarks from runs-on.com for CPU and I/O performance comparisons where applicable
"""


def main():
    query = create_research_query()
    initial_report_file = "report_for_beast2_ci/beast2_ci_final_report.md"
    # initial_report_file = "report_for_beast2_ci/beast2_ci_analysis_20260117_100000.md"

    with open(initial_report_file, "r", encoding="utf-8") as file:
        initial_report = file.read()

    report_path, summary_path = execute_main_process(
        query,
        output_path=OUTPUT_PATH,
        report_prefix="beast2_ci_analysis",
        task_name="investigate_beast2_ci",
        report_title="Beast2 CI Availability Improvement Options",
        thread_id="beast2_ci_improvement",
        recursion_limit=15,
        # initial_report=initial_report,
    )

    print(f"[✓] Report saved to: {report_path}")
    if summary_path:
        print(f"[✓] Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
