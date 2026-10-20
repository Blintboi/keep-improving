"""Windows-user-bound protection for local credentials; never a machine-wide key."""
import base64
import ctypes as C
from ctypes import wintypes as W
import os

PREFIX='dpapi:v1:'

class Blob(C.Structure):
    _fields_=[('size',W.DWORD),('data',C.POINTER(C.c_ubyte))]

def _crypt(data,encrypt):
    if os.name!='nt': raise OSError('Credential protection requires Windows.')
    crypt=C.WinDLL('crypt32',use_last_error=True); kernel=C.WinDLL('kernel32',use_last_error=True)
    source_buffer=C.create_string_buffer(data)
    context_buffer=C.create_string_buffer(b'GameTimeMonitor/local-credentials/v1')
    source=Blob(len(data),C.cast(source_buffer,C.POINTER(C.c_ubyte)))
    context=Blob(len(context_buffer)-1,C.cast(context_buffer,C.POINTER(C.c_ubyte))); output=Blob()
    if encrypt:
        operation=crypt.CryptProtectData
        operation.argtypes=[C.POINTER(Blob),W.LPCWSTR,C.POINTER(Blob),C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)]
        description='GameTimeMonitor credentials'
    else:
        operation=crypt.CryptUnprotectData
        operation.argtypes=[C.POINTER(Blob),C.c_void_p,C.POINTER(Blob),C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)]
        description=None
    operation.restype=W.BOOL
    kernel.LocalFree.argtypes=[C.c_void_p]; kernel.LocalFree.restype=C.c_void_p
    if not operation(C.byref(source),description,C.byref(context),None,None,1,C.byref(output)):
        raise OSError('The saved credential is unavailable on this Windows account.')
    try: return C.string_at(output.data,output.size)
    finally:
        C.memset(output.data,0,output.size); kernel.LocalFree(output.data)

def protect(value):
    if not isinstance(value,str) or len(value)>65536: raise ValueError('Invalid credential.')
    return PREFIX+base64.b64encode(_crypt(value.encode('utf-8'),True)).decode('ascii')

def unprotect(value):
    if not isinstance(value,str) or not value.startswith(PREFIX) or len(value)>131072: raise ValueError('Invalid saved credential.')
    try: return _crypt(base64.b64decode(value[len(PREFIX):],validate=True),False).decode('utf-8')
    except (ValueError,UnicodeError): raise ValueError('Invalid saved credential.') from None
