files = ['arch/x86/kvm/mmu/mmu_internal.h', 'arch/x86/kvm/mmu/mmu.c', 'arch/x86/include/asm/kvm_host.h', 'arch/x86/kvm/x86.c', 'arch/x86/kvm/mmu/tdp_mmu.c', 'arch/x86/kvm/mmu/tdp_mmu.h', 'arch/x86/kvm/vmx/vmx.c']

source = '/home/wangzc/Desktop/experiment/linux-source-5.13.0/'

dest = '/home/wangzc/Desktop/experiment/linux-source-5.13.0-kvm-shadow-ept/'

pwd = '/home/wangzc/Desktop/experiment/rationale-kvm-shadow-ept/src/'

for f in files:
    cmd = 'diff -u ' + source + f + "  " + dest + f + "  >  " + pwd + f + ".patch"
    print(cmd)