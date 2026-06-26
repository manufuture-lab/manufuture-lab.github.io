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
        Welcome to the ManuFuture Laboratory at Hanyang University, led by Prof. Sukkyung Kang. Our laboratory explores future manufacturing technologies at the intersection of advanced materials processing, surface and interface engineering, precision manufacturing, and data-driven process innovation. We aim to develop scientific understanding and practical engineering solutions for sustainable, intelligent, and high-performance manufacturing systems.

        We are always looking for motivated students and collaborators interested in shaping the future of manufacturing. [Join us →](/join/)
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
    
    design:
      spacing:
        padding: ["3rem", 0, "2rem", 0]
---
