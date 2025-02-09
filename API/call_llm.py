import json
from pydantic import BaseModel, Field
from typing import Dict, Any
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from langchain.output_parsers import PydanticOutputParser

load_dotenv()

rules = {
    "Max Height": 20,
    "Lowest Point": -5,
    "max number of floor": 4,
    "max total floor area": 1500,
    "max ground floor area": 250,
    "max facade length": 25,
    "Max number of floors underground": 1,
    "Max total floor to area ratio": 2,
    "Maximum ground floor to area ratio": 0.5,
}

class Compliance(BaseModel):
    passed_values: Dict[str, Any] = Field(
        description="Attributes that are within the specified limits."
    )
    failed_values: Dict[str, Any] = Field(
        description="Attributes that are not within the specified limits."
    )
    explanation: str = Field(
        description="A detailed explanation for why each attribute passed or failed."
    )

def extract_data_from_text(our_result_dict, temperature=0):
    our_result = json.dumps(our_result_dict, indent=4)
    jinja2_prompt_template = """
    You are an expert data extractor and compliance checker.

    **Mapping Note:**
    Sometimes the attribute names in the input differ from the rule names.
    Please use the following mapping to compare values:
    - "heighest" corresponds to the rule "Max Height"
    - "lowest" corresponds to "Lowest Point"
    - "number_of_floors" corresponds to "max number of floor"
    - "total_floor_area" corresponds to "max total floor area"
    - "ground_floor_area" corresponds to "max ground floor area"
    - "facade_length_1", "facade_length_2", "facade_length_3", "facade_length_4" correspond to "max facade length"
    - "number_of_underground_level" corresponds to "Max number of floors underground"

    **Task:**
    For each attribute in the input data, compare its value against the corresponding rule:
    1. If the value is within the allowed limit, add the attribute (with its value) to "passed_values".
    2. If the value violates the rule (i.e. exceeds a maximum or is below a minimum), add the attribute (with its value) to "failed_values".
    3. For each attribute, provide a detailed explanation in full sentences.
    - For example, for an attribute that fails, include:
        "The attribute 'heighest' has a value of 22.99 which exceeds the maximum allowed value of 20, so it fails."
    - For an attribute that passes, include:
        "The attribute 'lowest' has a value of -4.4 which is within the allowed range of -5 or above, so it passes."
    4. **Do not truncate the explanation.** Provide one complete sentence per attribute.

    **Input Data:**
    {{ our_result }}

    **Rules:**
    {{ rules }}

    Below is the JSON schema your output must conform to:
    {{ format_instructions }}

    **Example Output:**
    {
        "passed_values": {
            "lowest": "-4.4 passes because it is within the allowed minimum of -5",
            "ground_floor_area": "250 passes because it is exactly at the maximum allowed value of 250"
        },
        "failed_values": {
            "heighest": "22.99 fails because it exceeds the maximum allowed value of 20",
            "total_floor_area": "2053.13 fails because it exceeds the maximum allowed value of 1500"
        },
        "explanation": "For 'heighest', the value 22.99 exceeds the maximum allowed of 20; for 'total_floor_area', the value 2053.13 exceeds the maximum allowed of 1500; for 'lowest', the value -4.4 is within the acceptable range (>= -5); and for 'ground_floor_area', the value 250 meets the criteria."
    }
    """

    parser = PydanticOutputParser(pydantic_object=Compliance)
    prompt = PromptTemplate(
        template=jinja2_prompt_template,
        input_variables=["our_result", "rules", "format_instructions"],
        template_format="jinja2",  # IMPORTANT
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    generated_prompt = prompt.format(our_result=our_result, rules=rules)
    # print("Generated Prompt:")
    # print(generated_prompt)
    print("-" * 80)

    llm = OpenAI(temperature=temperature)

    chain = prompt | llm | parser
    result = chain.invoke({"our_result": our_result, "rules": rules})

    answer = {
        'passed': result.passed_values,
        'failed': result.failed_values,
        'explanation': result.explanation
    }

    print("LLM Parsed Response:")
    print(answer)
    print("Full Raw Result:")
    print(result)
    print("JSON Formatted Parsed Output:")
    print(json.dumps(answer, indent=4))

    return answer

if __name__ == '__main__':
    our_result_data = {
        "heighest": 22.994157028775764,
        "lowest": -4.4,
        "number_of_floors": 7,
        "total_floor_area": 2053.1270080472705,
        "ground_floor_area": 233.84898800000002,
        "facade_length_1": 21.908858409427527,
        "facade_length_2": 19.63500000000002,
        "facade_length_3": 21.908858409427527,
        "facade_length_4": 19.63500000000002,
        "number_of_underground_level": 1,
        "Total floor to area ratio": 2,
        "Ground floor to area ratio": 0.5,
    }
    compliance_data = extract_data_from_text(our_result_data)
    print("Final Parsed Compliance Data:")
    print(compliance_data)
