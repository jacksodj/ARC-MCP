"""
Response Rewriter
Rewrites LLM responses based on ARC validation findings
"""
from typing import Dict, Any, Optional, List
import logging
from handlers.template_manager import TemplateManager
from handlers.rewrite_utils import FindingProcessor, FindingType


class ResponseRewriter:
    """Rewrites responses based on ARC validation findings"""

    def __init__(
        self,
        policy_definition: Optional[str] = None,
        template_dir: str = "response_rewriting_prompts",
        domain: str = "General"
    ):
        """
        Initialize ResponseRewriter.

        Args:
            policy_definition: Optional policy text for context
            template_dir: Directory containing prompt templates
            domain: Domain context (e.g., "Healthcare", "Finance")
        """
        self.domain = domain
        self.template_manager = TemplateManager(template_dir)
        self.finding_processor = FindingProcessor(policy_definition)
        self.logger = logging.getLogger(__name__)

    def prepare_rewrite_prompt(
        self,
        user_query: str,
        llm_response: str,
        finding_type: FindingType,
        relevant_findings: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Prepare a rewrite prompt for a specific finding type.

        Args:
            user_query: Original user question
            llm_response: Original LLM response to rewrite
            finding_type: Type of finding to address
            relevant_findings: List of findings of this type

        Returns:
            Formatted prompt string or None if no template available
        """
        template = self.template_manager.get_template(finding_type)
        if not template:
            return None

        # Base template variables
        template_vars = {
            "domain": self.domain,
            "question": user_query,
            "original_answer": llm_response
        }

        # Add finding-specific data
        finding_data = self.finding_processor.process_finding_data(
            finding_type, relevant_findings
        )
        template_vars.update(finding_data)

        return self.template_manager.format_template(template, **template_vars)

    def rewrite_response(
        self,
        user_query: str,
        llm_response: str,
        ar_findings: Dict[str, Any],
        model_id: str,
        bedrock_runtime_client
    ) -> Dict[str, Any]:
        """
        Rewrite response handling multiple finding types.

        Args:
            user_query: Original user question
            llm_response: Original LLM response
            ar_findings: Automated reasoning findings from guardrail
            model_id: Bedrock model ID for rewriting
            bedrock_runtime_client: Boto3 bedrock-runtime client

        Returns:
            Dict containing rewrite results and metadata
        """
        result = {
            "original_response": llm_response,
            "rewritten": False,
            "finding_types": [],
            "findings_count": 0,
            "rewritten_response": None,
            "message": None
        }

        # Check if we have findings to process
        if not ar_findings or "findings" not in ar_findings or not ar_findings["findings"]:
            result["message"] = "No findings to process"
            return result

        # Categorize findings by type
        findings_by_type = self.finding_processor.categorize_findings(
            ar_findings["findings"]
        )
        priority_types = self.finding_processor.get_priority_types(findings_by_type)

        if not priority_types:
            result["message"] = "No actionable findings"
            return result

        # Special handling: TOO_COMPLEX as the only finding
        if priority_types == [FindingType.TOO_COMPLEX]:
            result["finding_types"] = [FindingType.TOO_COMPLEX.key]
            result["findings_count"] = len(findings_by_type.get(FindingType.TOO_COMPLEX, []))
            result["rewritten"] = True
            result["rewritten_response"] = (
                "This question contains too much information to process accurately. "
                "Please break it down into simpler, more focused questions."
            )
            result["message"] = "Replaced with generic TOO_COMPLEX message"
            return result

        # Special handling: VALID as the only finding (no rewrite needed)
        if priority_types == [FindingType.VALID]:
            result["finding_types"] = [priority_types[0].key]
            result["message"] = f"No rewrite needed. Finding type: {priority_types[0].key}"
            result["findings_count"] = len(findings_by_type.get(priority_types[0], []))
            return result

        # Process each finding type in priority order
        rewrites = []
        for finding_type in priority_types:
            relevant_findings = findings_by_type[finding_type]
            prompt = self.prepare_rewrite_prompt(
                user_query, llm_response, finding_type, relevant_findings
            )

            if prompt:
                try:
                    self.logger.info(f"Rewriting for finding type: {finding_type.key}")

                    response = bedrock_runtime_client.converse(
                        modelId=model_id,
                        messages=[{"role": "user", "content": [{"text": prompt}]}]
                    )

                    rewritten_text = response['output']['message']['content'][0]['text']
                    rewrites.append({
                        "finding_type": finding_type.key,
                        "rewritten_text": rewritten_text
                    })
                    result["finding_types"].append(finding_type.key)
                    result["findings_count"] += len(relevant_findings)

                except Exception as e:
                    self.logger.error(f"Error rewriting for {finding_type.key}: {e}")
                    continue

        # Combine rewrites if we have any
        if rewrites:
            if len(rewrites) == 1:
                # Single finding type - use the rewrite directly
                result["rewritten_response"] = rewrites[0]["rewritten_text"]
                result["rewritten"] = True
                result["message"] = f"Successfully rewrote response for {rewrites[0]['finding_type']}"
            else:
                # Multiple finding types - combine them
                combined_response = self._combine_rewrites(
                    user_query, llm_response, rewrites, bedrock_runtime_client, model_id
                )

                if combined_response:
                    result["rewritten_response"] = combined_response
                    result["rewritten"] = True
                    result["message"] = f"Successfully rewrote response for: {', '.join(result['finding_types'])}"
                else:
                    result["message"] = "Error combining rewrites"
        else:
            result["message"] = "No rewrites generated"

        return result

    def _combine_rewrites(
        self,
        user_query: str,
        llm_response: str,
        rewrites: List[Dict[str, str]],
        bedrock_runtime_client,
        model_id: str
    ) -> Optional[str]:
        """
        Combine multiple rewrites into a single coherent response.

        Args:
            user_query: Original question
            llm_response: Original response
            rewrites: List of rewrite dictionaries
            bedrock_runtime_client: Boto3 client
            model_id: Model ID for combination

        Returns:
            Combined response text or None on error
        """
        combine_prompt = f"""Your task is to combine multiple corrected answers into a single coherent response.

Original Question: {user_query}

Original Answer: {llm_response}

The following are corrected versions addressing different issues:

"""
        for i, rewrite in enumerate(rewrites, 1):
            combine_prompt += f"Correction {i} ({rewrite['finding_type']}): {rewrite['rewritten_text']}\n\n"

        combine_prompt += """
Create a single unified response that:
1. Directly answers the question without any meta-commentary
2. Combines all corrections without redundancy or overlap
3. Does NOT include phrases like "here's a comprehensive response" or "addressing both issues"
4. Does NOT add any new information beyond what's in the corrections
5. Maintains a natural, conversational tone

Your response should begin immediately with the answer.
"""

        try:
            response = bedrock_runtime_client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": combine_prompt}]}]
            )

            return response['output']['message']['content'][0]['text']

        except Exception as e:
            self.logger.error(f"Error combining rewrites: {e}")
            return None
