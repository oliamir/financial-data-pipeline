
import os
import yaml
import re

class AgentManager:
    """
    Manages loading and retrieving subagent personas from markdown definitions.
    """
    
    def __init__(self, agents_dir=".claude/agents"):
        # Resolve path relative to CWD or project root
        self.agents_dir = agents_dir
        if not os.path.exists(self.agents_dir):
            # Try finding it relative to project root if running from bin/ or src/
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            candidate = os.path.join(project_root, ".claude/agents")
            if os.path.exists(candidate):
                self.agents_dir = candidate
        
        self.agents = {}
        self._load_agents()

    def _load_agents(self):
        """Scans the agents directory and indexes available agents."""
        if not os.path.exists(self.agents_dir):
            print(f"Warning: Agents directory '{self.agents_dir}' not found.")
            return

        for filename in os.listdir(self.agents_dir):
            if filename.endswith(".md"):
                agent_name = filename[:-3] # Remove .md
                self.agents[agent_name] = os.path.join(self.agents_dir, filename)

    def list_agents(self):
        """Returns list of available agent names."""
        return sorted(list(self.agents.keys()))

    def get_agent_prompt(self, agent_name):
        """
        Parses the agent MD file to extract system prompt.
        Format is typically YAML frontmatter (between ---) followed by prompt.
        """
        if agent_name not in self.agents:
            return None
        
        file_path = self.agents[agent_name]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Subagent files often have YAML frontmatter
            # and the rest is the system prompt.
            
            parts = re.split(r'^---\s*$', content, maxsplit=2, flags=re.MULTILINE)
            
            if len(parts) >= 3:
                # [0] is empty (before first ---)
                # [1] is yaml
                # [2] is prompt
                # metadata = yaml.safe_load(parts[1])
                prompt = parts[2].strip()
                return prompt
            else:
                # No frontmatter? Return whole content
                return content.strip()
                
        except Exception as e:
            print(f"Error loading agent {agent_name}: {e}")
            return None
