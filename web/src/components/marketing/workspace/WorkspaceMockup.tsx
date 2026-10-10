"use client";

import WorkspaceHeader from "./WorkspaceHeader";
import ChatArea from "./ChatArea";
import RightSidebar from "./RightSidebar";

export default function WorkspaceMockup() {
    return (
        <div className="relative">

            <div className="absolute inset-0 -z-10 flex items-center justify-center">

                <div className="h-[550px] w-[550px] rounded-full bg-primary/20 blur-[140px]" />

            </div>

            <div className="overflow-hidden rounded-md border border-white/10 bg-background/80 shadow-md backdrop-blur-xl">

                <WorkspaceHeader />

                <div className="grid grid-cols-[1fr_300px]">

                    <div className="p-6">

                        <ChatArea />

                    </div>

                    <aside className="border-l bg-muted/30 p-5">

                        <RightSidebar />

                    </aside>

                </div>

            </div>

        </div>
    );
}