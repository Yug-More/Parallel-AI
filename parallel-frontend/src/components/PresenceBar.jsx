// src/components/PresenceBar.jsx
export default function PresenceBar() {
  return (
    <div
      style={{
        width: "100%",
        height: "55px",
        display: "flex",
        alignItems: "center",
        paddingLeft: "22px",
        color: "#bbb",
        fontSize: "16px",
        backdropFilter: "blur(12px)",
      }}
    >
      Online: Yug • Severin • Sean • Nayab
    </div>
  );
}
