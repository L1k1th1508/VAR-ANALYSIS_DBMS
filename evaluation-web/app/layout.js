import "./style.css";
export const metadata = {
  title: "Referee & VAR | Evaluation Portal",
  description: "Source-backed football analytics and research notebook",
};
export default function Layout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
