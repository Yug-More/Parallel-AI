# spoon_official.py
# Official Spoon OS graph wiring (Linux container recommended).
# Requires: pip install spoon-ai-sdk spoon-cli
from typing import Dict, Optional, TypedDict, List
from spoon_ai.graph import StateGraph
from openai import OpenAI
from config import CLIENTS, OPENAI_MODEL

class TeamState(TypedDict, total=False):
    asker: str
    prompt: str
    sys_ctx: str
    mode: str
    target: Optional[str]
    drafts: Dict[str, str]
    synthesis: str

TEAM_ORDER = ["yug","sean","severin","nayab"]

def _chat(agent_id: str, messages: List[Dict[str, str]], temperature: float = 0.35) -> str:
    client: OpenAI = CLIENTS[agent_id]
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content

def build_team_graph() -> StateGraph:
    graph = StateGraph(TeamState)

    def ask_one(state: TeamState) -> Dict:
        member = state.get("target") or "yug"
        asker = state["asker"]; prompt = state["prompt"]; sys_ctx = state["sys_ctx"]
        out = _chat(member, [
            {"role":"system","content": sys_ctx},
            {"role":"user","content": f"{asker} asks {member.title()}:\n{prompt}"}
        ], temperature=0.35)
        return {"drafts": {member: out}}

    def ask_team(state: TeamState) -> Dict:
        asker = state["asker"]; prompt = state["prompt"]; sys_ctx = state["sys_ctx"]
        drafts: Dict[str,str] = {}
        for m in TEAM_ORDER:
            drafts[m] = _chat(m, [
                {"role":"system","content": sys_ctx},
                {"role":"system","content": f"You are {m.title()}. Provide your perspective."},
                {"role":"user","content": f"Team question from {asker}:\n{prompt}"}
            ], temperature=0.4)
        return {"drafts": drafts}

    def synthesize(state: TeamState) -> Dict:
        drafts = state["drafts"]; sys_ctx = state["sys_ctx"]
        msgs: List[Dict[str,str]] = [
            {"role":"system","content":"You are the coordinator. Synthesize the drafts into one clear answer with 2–5 next steps. If the project summary should be updated, end with:\n\nSUMMARY_UPDATE:\n<1–3 sentences>"},
            {"role":"system","content": sys_ctx},
            {"role":"user","content": f"Latest human message from {state['asker']}:\n{state['prompt']}"}
        ]
        for who, text in drafts.items():
            msgs.append({"role":"assistant","content": f"{who.title()} draft:\n{text}"})
        synth = _chat("coordinator", msgs, temperature=0.3)
        return {"synthesis": synth}

    graph.add_node("ask_one", ask_one)
    graph.add_node("ask_team", ask_team)
    graph.add_node("synthesize", synthesize)
    return graph
