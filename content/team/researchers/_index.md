---
title: "Researchers"
date: 2026-06-07
type: landing

design:
  spacing: "6rem"

sections:
  - block: markdown
    id: graduate-students
    content:
      title: "Graduate Students"
      text: |
        {{< mfl-members "graduate" >}}
    design:
      spacing:
        padding: ["2rem", 0, "2rem", 0]
      css_class: "mfl-members-section"
      css_style: "max-width: 100% !important; width: 100% !important;"
      container: false

  - block: markdown
    id: undergraduate-students
    content:
      title: "Undergraduate Students"
      text: |
        {{< mfl-members "undergraduate" >}}
    design:
      spacing:
        padding: ["2rem", 0, "2rem", 0]
      css_class: "mfl-members-section"
      css_style: "max-width: 100% !important; width: 100% !important;"
      container: false

  - block: markdown
    id: alumni
    content:
      title: "Alumni"
      text: |
        {{< mfl-members "alumni" >}}
    design:
      spacing:
        padding: ["2rem", 0, "2rem", 0]
      css_class: "mfl-members-section"
      css_style: "max-width: 100% !important; width: 100% !important;"
      container: false
---
