# rationale-kvm-shadow-ept

![KVM MMU EPT内存管理](https://blog.csdn.net/xelatex_kvm/article/details/17685123)  
![KVM地址翻译流程及EPT页表的建立过程](https://blog.csdn.net/lux_veritas/article/details/9284635)  
![xelatex KVM-KVM相关](https://blog.csdn.net/xelatex_kvm/category_1823953.html)


kvm，死循环进入guest，直到exit退出，最重要的路径是 **kvm_vcpu_ioctl -> kvm_arch_vcpu_ioctl_run -> vcpu_run（死循环） -> vcpu_enter_guest(arch/x86/kvm/x86.c死循环)**

理解这个几乎理解的kvm


# ept pgd 到底load了多少次

```
sudo bpftrace -e 'kfunc:kvm_mmu_create { printf("kvm_mmu_create: %s  %016lx %016lx\n", comm, args->vcpu, (struct kvm_vcpu*)(args->vcpu)->requests);  @a[kstack()] = count();}'

@a[
    cleanup_module+332963
    cleanup_module+332963
    ftrace_trampoline+24621
    kvm_mmu_create+5
    kvm_vm_ioctl+2020
    __x64_sys_ioctl+145
    do_syscall_64+97
    entry_SYSCALL_64_after_hwframe+68
]: 8


sudo bpftrace -e 'kfunc:vmx_load_mmu_pgd { printf("kfunc:vmx_load_mmu_pgd: %s  %016lx  %016lx  %d\n", comm, args->vcpu, args->root_hpa, args->root_level);  @b[kstack()] = count();  } '

sudo bpftrace -e 'kfunc:kvm_mmu_load {printf("kfunc:kvm_mmu_load: %s  %016lx\n", comm, args->vcpu);  @c[kstack()] = count();   }'


sudo bpftrace -e 'kfunc:vmx_load_mmu_pgd { printf("kfunc:vmx_load_mmu_pgd: %s  %016lx  %016lx  %d\n", comm, args->vcpu, args->root_hpa, args->root_level);  @b[kstack()] = count();  }    kfunc:kvm_mmu_load {printf("kfunc:kvm_mmu_load: %s  %016lx\n", comm, args->vcpu);  @c[kstack()] = count();   }'


@b[
    ftrace_trampoline+71173
    ftrace_trampoline+71173
    nfnetlink_exit+20075
    vmx_load_mmu_pgd+5
    kvm_arch_vcpu_ioctl_run+2502
    kvm_vcpu_ioctl+579
    __x64_sys_ioctl+145
    do_syscall_64+97
    entry_SYSCALL_64_after_hwframe+68
]: 36866

@c[
    cleanup_module+331118
    cleanup_module+331118
    cleanup_module+391158
    kvm_mmu_load+5
    kvm_vcpu_ioctl+579
    __x64_sys_ioctl+145
    do_syscall_64+97
    entry_SYSCALL_64_after_hwframe+68
]: 36866


sudo bpftrace -e 'kfunc:construct_eptp { printf("kfunc:construct_eptp: %s  %016lx  %016lx  %d\n", comm, args->vcpu, args->root_hpa, args->root_level);  @d[kstack()] = count(); }'  没有捕获到运行行为，直接插桩试试看

sudo bpftrace -e 'kfunc:vmx_load_mmu_pgd { printf("kfunc:vmx_load_mmu_pgd: %s  %016lx  %016lx  %d\n", comm, args->vcpu, args->root_hpa, args->root_level);  @b[kstack()] = count();  }    kfunc:kvm_mmu_load {printf("kfunc:kvm_mmu_load: %s  %016lx\n", comm, args->vcpu);  @c[kstack()] = count();   }   kfunc:construct_eptp { printf("kfunc:construct_eptp: %s  %016lx  %016lx  %d\n", comm, args->vcpu, args->root_hpa, args->root_level);  @d[kstack()] = count(); }'


sudo bpftrace -e 'kfunc:vmx_vcpu_run { printf("kfunc:vmx_vcpu_run: %s  %016lx\n", comm, args->vcpu);  @e[kstack()] = count(); }'

@e[
    realtek_driver_exit+209770
    realtek_driver_exit+209770
    realtek_driver_exit+329718
    vmx_vcpu_run+5
    kvm_vcpu_ioctl+579
    __x64_sys_ioctl+145
    do_syscall_64+97
    entry_SYSCALL_64_after_hwframe+68
]: 41918301


sudo bpftrace -e 'kfunc:kvm_set_cr3 { printf("kfunc:kvm_set_cr3: %s  %016lx  %016lx\n", comm, args->vcpu, args->cr3); @f[kstack()] = count();}'


sudo bpftrace -e 'kfunc:kvm_set_cr3 { printf("kfunc:kvm_set_cr3: %s  %016lx  %016lx\n", comm, args->vcpu, args->cr3); @f[kstack()] = count();}  kfunc:vmx_load_mmu_pgd { printf("kfunc:vmx_load_mmu_pgd: %s  %016lx  %016lx  %d\n", comm, args->vcpu, args->root_hpa, args->root_level);  @b[kstack()] = count();  }    kfunc:kvm_mmu_load {printf("kfunc:kvm_mmu_load: %s  %016lx\n", comm, args->vcpu);  @c[kstack()] = count();   }'



sudo bpftrace -e 'kfunc:kvm_mmu_reset_context{ printf("kvm_mmu_reset_context:%s %016lx\n", comm, args->vcpu); @[kstack()] = count();}'

```



# 调用路径查看
bpftrace 

`kfunc:kvm_mmu_load` 还调用了 `kvm_mmu_load_pgd`,被`kvm_mmu_reload` 内联包裹了


重要的宏，把一系列 `vmx_xxx`转换成 `static_call(kvm_x86_xxx)(arguments)`
```
#define KVM_X86_OP(func)					     \
	DEFINE_STATIC_CALL_NULL(kvm_x86_##func,			     \
				*(((struct kvm_x86_ops *)0)->func));
#define KVM_X86_OP_NULL KVM_X86_OP
```

现在有个问题

- windows 大概率频繁触发

那发生ept violation是什么处理途径呢

`kvm_vmx_exit_handlers[]` handler数组，在`arch/x86/kvm/vmx/vmx.c`

kvm_vcpu_ioctl -> kvm_arch_vcpu_ioctl_run -> vcpu_run ->  `vcpu_enter_guest` -> `vmx_x86_ops.handle_exit` -> `vmx_handle_exit` -> `__vmx_handle_exit`



sudo bpftrace -e 'kfunc:vmx_vcpu_run {printf("%s %016lx\n", comm, args->vcpu); @[kstack()]=count(); }'
@[
    cleanup_module+331938
    cleanup_module+331938
    ftrace_trampoline+24621
    vmx_vcpu_run+5
    kvm_vcpu_ioctl+579
    __x64_sys_ioctl+145
    do_syscall_64+97
    entry_SYSCALL_64_after_hwframe+68
]: 1112542


kvm_vcpu_ioctl -> kvm_arch_vcpu_ioctl_run -> vcpu_run -> vcpu_enter_guest -> `exit_fastpath = static_call(kvm_x86_run)(vcpu);` 触发，中间内容省略了

<!-- kvm_vcpu_ioctl -> vmx_vcpu_run 实际发生的 -->