#!/usr/bin/env python3
import time
import os
import sys

print("hello world")
print(f"MY_VAR: {os.getenv('MY_VAR')}")
time.sleep(10)
sys.exit(1)


#import time
#import sys

#try:
#    print("hello world")
#    time.sleep(10)
#    sys.exit(0)  # Успешное завершение
#except Exception as e:
#    print(f"An error occurred: {e}", file=sys.stderr)
#    sys.exit(1)  # Завершение с ошибкой
