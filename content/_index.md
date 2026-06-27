---
title: "Home"
date: 2023-10-24
type: landing

design:
  spacing: "6rem"

sections:
  - block: hero
    content:
      announcement:
        badge:
          text: NEW
          color: primary
        text: "We are recruiting students and interns."
        link:
          text: "Apply"
          url: "/join/"

      title: |-
        ManuFuture Laboratory
        @ Hanyang University

      text: "한양대학교 미래제조 연구실"

    design:
      spacing:
        padding: [0, 0, 0, 0]
        margin: [0, 0, 0, 0]
      css_class: "dark whitespace-pre-line mfl-hero"
      background:
        color: "#0a0e27"
        image:
          filename: "home.png"
          filters:
            brightness: 0.55
          size: cover
          position: center
          parallax: false

  - block: markdown
    id: intro
    content:
      title: ""
      text: |
        Welcome to the ManuFuture Laboratory at Hanyang University. Led by Prof. Sukkyung Kang, we pioneer frontier manufacturing by understanding and precisely controlling the fundamental mechanisms of friction, wear, and deformation at surfaces and interfaces.<br>
        We welcome motivated students and collaborators who are eager to shape the future of manufacturing. [Join us →](/join/)

    design:
      spacing:
        padding: ["3rem", 0, "2rem", 0]
      css_class: "mfl-home-intro-section"
      css_style: "max-width: 100% !important; width: 100% !important;"
      container: false

  - block: markdown
    id: home-research-area
    content:
      title: ""
      text: |
        {{< mfl-research-areas layout="carousel" >}}

    design:
      spacing:
        padding: ["2rem", 0, "2rem", 0]
      css_class: "mfl-home-research-section"
      css_style: "max-width: 100% !important; width: 100% !important;"
      container: false
---
