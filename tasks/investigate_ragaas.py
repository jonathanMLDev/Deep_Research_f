"""
RAGaaS Platform Investigation Module

Simplified to delegate research execution to main_process.execute_main_process.
"""

from deep_research.main_process import execute_main_process

OUTPUT_PATH = "report_by_ragaas"


def create_query_for_rag() -> str:
    return """Research top 6-8 RAGaaS (Retrieval-Augmented Generation as a Service) platforms suitable for a C++ Copilot use case.

Use Case: C++ Copilot - AI assistant for C++ development with code understanding, documentation, and technical Q&A capabilities.

Requirements:
- Data types: HTML, JSON, PDF, MD, TXT, ADOC, code files (C++, header files, etc.)
- Hybrid retrieval methods (semantic + keyword/BM25, vector + graph, etc.)
- Possible to filter by metadata such as:
    data source like as mailing list, slack, github code, documentation website, etc.
    framework, language, date range, etc.
    creator, company, etc.
- Sophisticated system prompts with customization
- High accuracy for QA and summarization tasks
- User-customizable configurations (retrieval strategies, prompts, models)
- Modern RAG capabilities: graph RAG, multi-hop reasoning, structured data handling
- Data scale: ~50GB (approximately 3 million documents)
- Support for code-specific understanding and technical documentation

Provide a CONCISE, OBJECTIVE, and QUANTITATIVE report (max 1000 words) with SHORT paragraphs (2-4 sentences max).

**CRITICAL: CONCISENESS REQUIREMENTS:**
- Keep paragraphs SHORT (2-4 sentences maximum)
- Use bullet points and tables liberally for better readability
- Avoid long, dense paragraphs - break information into digestible chunks
- Prioritize key insights over exhaustive detail
- Remove redundant information
- Do not use bold formatting and quotation marks within a sentence.

1. **Top 6-8 RAGaaS Platforms** (use bullet points, keep each platform to 4-5 bullet points):
   For each platform, provide:
   - Platform name, company, website URL, pricing model (if available)
   - Key strengths for C++ Copilot use case
   - Main limitations or concerns
   - Supported data formats and file types
   - Retrieval methods (semantic, keyword, hybrid, graph RAG, etc.)
   - Customization capabilities (system prompts, retrieval parameters, model selection)
   - Data scale limits and pricing tiers (if available)

2. **Quantitative Feature Comparison Table**:
   Create a comprehensive comparison table with these metrics for each platform:
   - **Data Format Support**: HTML, JSON, PDF, MD, TXT, ADOC, code files (C++/header files)
   - **Retrieval Methods**: Semantic search, keyword/BM25, hybrid, graph RAG, multi-hop reasoning
   - **Customization**: System prompt editing, retrieval parameter tuning, model selection, custom embeddings
   - **Scale Capacity**: Max documents, max data size, pricing per document/GB
   - **Accuracy Metrics**: QA accuracy (if available), summarization quality, code understanding capabilities
   - **Modern RAG Features**: Graph RAG, structured data extraction, code-specific parsing, multi-modal support
   - **API & Integration**: REST API, SDK availability, webhook support, real-time updates
   - **Performance**: Query latency, indexing speed, concurrent request limits

   Use actual numbers when available, or "—" if not available. Be objective and data-driven.

3. **Summary Comparison Table**:
   Create a concise table with columns:
   | Platform | Best For | Main Advantage | Main Limitation | Graph RAG Support | Customization Level | Pricing Model |

4. **C++ Copilot Suitability Analysis** (2-3 short paragraphs max):
   - Which platforms are best suited for code understanding and C++ documentation
   - Support for code-specific features (syntax highlighting, code parsing, AST understanding)
   - Integration capabilities with development environments
   - Handling of technical documentation and code examples

5. **Modern RAG Capabilities** (2-3 short paragraphs max):
   - Graph RAG implementation and maturity
   - Multi-hop reasoning and complex query handling
   - Structured data extraction from code and documentation
   - Support for hierarchical and relational data (code dependencies, documentation structure)

6. **Scale and Performance** (2-3 short paragraphs max):
   - How each platform handles ~50GB / 3M documents
   - Indexing performance and update mechanisms
   - Query latency and throughput for large-scale deployments
   - Cost implications for the specified data volume

7. **Recent Trends (2023-2025)** - Brief summary (2-3 short paragraphs max):
   - Platform evolution and new feature releases
   - Industry adoption trends
   - Emerging capabilities in graph RAG and code understanding

8. **Conclusion** - Objective assessment (2-3 short paragraphs max):
   - Top 2-3 recommended platforms for C++ Copilot use case
   - Key trade-offs based on requirements (data types, scale, customization, modern RAG features)
   - Implementation considerations and migration paths

Focus on objective, quantitative data. Include specific numbers, dates, pricing information, and technical metrics when available. Prioritize platforms with strong graph RAG capabilities, code understanding features, and high customization options. Keep the report concise and scannable."""


def main():
    query = create_query_for_rag()
    report_path, summary_path = execute_main_process(
        query,
        output_path=OUTPUT_PATH,
        report_prefix="ragaas_analysis",
        task_name="investigate_ragaas",
        report_title="RAGaaS Platform Analysis for C++ Copilot",
        thread_id="ragaas_platforms_analysis",
        recursion_limit=15,
    )

    print(f"[✓] Report saved to: {report_path}")
    if summary_path:
        print(f"[✓] Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
