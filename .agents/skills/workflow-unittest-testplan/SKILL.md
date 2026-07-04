---
name: workflow-unittest-testplan
description: Describes how to write test cases and test plans for unit testing. Covers use cases, edge cases, and business-critical scenarios.
whenToUse: writing unit test
---

# Goal
- Define unit test writing form
- Define code coverage rule

# Requirements
- list of class and method you need to cover
- list of usecases

# How to use it
1. Prepare list of usecases which you need to cover. 
  1. Follow [code coverage skill](.agents/skills/code-coverage/SKILL.md)
  2. Cover corner cases, edge cases, and happy path.
  3. Cover cases which are easy to be missed by developers. For example, if there is a method which has a parameter with default value, you need to cover the case when the parameter is not passed.
  4. Cover cases which are easy to be wrong. For example, if there is a method which has a parameter with default value, you need to cover the case when the parameter is passed with wrong value.
  5. Cover cases which are important for business. For example, if there is a method which is used to calculate the price of a product, you need to cover the case when the price is negative.
  6. Cover cases which are important for performance. For example, if there is a method which is used to process a large amount of data, you need to cover the case when the data is large.
  7. Cover cases which are important for security. For example, if there is a method which is used to validate the input, you need to cover the case when the input is malicious.
2. Use @./templates/usecases_list.md template to show them to user for confirmation