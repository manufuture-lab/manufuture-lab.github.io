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
          filename: "home.jpeg"
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
        We welcome motivated students and collaborators who are eager to shape the future of manufacturing. [Join us →](/join/) <br><br>
        저희 연구실은 표면과 계면에서 발생하는 마찰, 마모, 변형 현상을 이해하고 제어하여, 미래 제조기술의 새로운 패러다임을 제시하는 연구를 수행하고 있습니다. 특히 반도체 제조 분야를 중심으로 초정밀 연마, 세정 등 높은 정밀도와 신뢰성이 요구되는 제조기술을 개발하고, 이를 위한 핵심 원천기술을 확보하는 것을 목표로 합니다. 나아가 이러한 제조 원리와 공정 기술을 자동차, 배터리, 소프트 디바이스 등 다양한 산업 분야로 확장하여, 고성능, 고신뢰성, 지능형 미래 제조기술을 개발하고자 합니다. 열정적인 학생과 연구자, 그리고 협력 파트너를 언제나 환영합니다.

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
