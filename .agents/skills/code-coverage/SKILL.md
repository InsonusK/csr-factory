---
name: code-coverage
description: How many codes must be codered by unittest
whenToUse: write code or write test
---

# How to use it
1. Unittest test is required. Unless user ask to skip it. 
2. You must cover 80+% of code.
3. You could skill testing parts or logic branches which raise exceptions and doesn't change data

Example: 
**Could skip**
- just raising exception
```python
if A > B:
    raise RuntimeError("Some error")
```
- raising exception with writing log
```python
if A > B:
    print("some text")
    raise RuntimeError("Some error")
```
**Should cover by tests**
- Break logic
```python
if A > B:
    pass
```
```python
if A > B:
    break
```
- raising exception BUT change values
```python
if A > B:
    A = 10
    raise RuntimeError("Some error")
```