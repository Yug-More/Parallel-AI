// Mock API functions for IDE endpoints
// These will be replaced with real FastAPI endpoints later

export interface Collaborator {
  id: string;
  name: string;
  role: string;
  status: "active" | "idle" | "offline";
  apiKey?: string; // For backend reference
}

export interface EditorCell {
  id: string;
  type: "code" | "markdown";
  content: string;
  output?: string;
  language?: string;
  isRunning?: boolean;
}

export interface ChatMessage {
  id: string;
  sender: string;
  senderId: string;
  text: string;
  timestamp: Date;
}

// Mock collaborators
const mockCollaborators: Collaborator[] = [
  { id: "1", name: "Sean", role: "UI Specialist", status: "active" },
  { id: "2", name: "Severin", role: "Backend Engineer", status: "idle" },
  { id: "3", name: "Yug", role: "AI Agent Logic", status: "active" },
  { id: "4", name: "Alex", role: "DevOps", status: "offline" },
];

// Mock API functions
export async function getCollaborators(): Promise<Collaborator[]> {
  // Simulate API delay
  await new Promise((resolve) => setTimeout(resolve, 300));
  return [...mockCollaborators];
}

export async function sendChatMessage(
  collaboratorId: string,
  message: string
): Promise<ChatMessage> {
  // Simulate API delay
  await new Promise((resolve) => setTimeout(resolve, 500));
  
  const collaborator = mockCollaborators.find((c) => c.id === collaboratorId);
  return {
    id: Date.now().toString(),
    sender: collaborator?.name || "Agent",
    senderId: collaboratorId,
    text: `Mock response from ${collaborator?.name || "agent"}: "${message}"`,
    timestamp: new Date(),
  };
}

export async function executeCell(cellId: string, code: string): Promise<string> {
  // Simulate code execution delay
  await new Promise((resolve) => setTimeout(resolve, 800));
  
  // Mock output
  return `Output for cell ${cellId}:\nExecuted: ${code.substring(0, 50)}...\n[Mock execution result]`;
}

export async function saveCell(cellId: string, content: string): Promise<void> {
  // Simulate save delay
  await new Promise((resolve) => setTimeout(resolve, 200));
  console.log(`Saved cell ${cellId}`);
}

export async function deleteCell(cellId: string): Promise<void> {
  // Simulate delete delay
  await new Promise((resolve) => setTimeout(resolve, 200));
  console.log(`Deleted cell ${cellId}`);
}

export async function addCell(
  type: "code" | "markdown",
  position?: number
): Promise<EditorCell> {
  // Simulate API delay
  await new Promise((resolve) => setTimeout(resolve, 200));
  
  return {
    id: Date.now().toString(),
    type,
    content: type === "code" ? "# Your code here" : "# Markdown cell",
    language: type === "code" ? "python" : undefined,
  };
}

