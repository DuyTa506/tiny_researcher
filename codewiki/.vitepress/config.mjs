import { withMermaid } from "vitepress-plugin-mermaid"
import sidebar from "./sidebar.mjs"

export default withMermaid({
  title: 'research_assistant',
  description: 'CodeWiki generated from source code',
  cleanUrls: true,
  themeConfig: {
    nav: [
      { text: "Overview", link: "/overview" }
    ],
    sidebar,
    outline: {
      level: [2, 3, 4]
    },
    outlineTitle: 'On this page'
  },
  mermaid: {}
})
