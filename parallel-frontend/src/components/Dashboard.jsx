import Background3D from "./Background3D";
import Sidebar from "./Sidebar";
import FloatingAvatars from "./FloatingAvatars";
import UserPanel from "./UserPanel";
import CommandBar from "./CommandBar";

export default function Dashboard() {
  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <Background3D />
      <Sidebar />

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          position: "relative",
        }}
      >
        <FloatingAvatars />

        <div
          style={{
            flex: 1,
            display: "grid",
            gap: "28px",
            padding: "32px",
            gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))",
            overflowY: "auto",
          }}
        >
          <UserPanel name="Yug" isSelf />
          <UserPanel name="Severin" />
          <UserPanel name="Sean" />
          <UserPanel name="Nayab" />
        </div>

        <CommandBar />
      </div>
    </div>
  );
}
