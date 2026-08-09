// components/SidebarItemList.jsx
import React from "react";
import { Link, useLocation } from "react-router";
import {
  Database,
  Settings,
  FileText,
  BarChart3,
  User,
  CreditCard,
  DollarSign,
} from "lucide-react";

export const sidebarItems = [
  { icon: <Database className="w-5 h-5" />, label: "Query Builder", to: "/querybuilder" },
  { icon: <Settings className="w-5 h-5" />, label: "Database Setup", to: "/database-setup" },
  { icon: <FileText className="w-5 h-5" />, label: "SQL Assistants", to: "/sql-assistants" },
  { icon: <BarChart3 className="w-5 h-5" />, label: "Dashboard", to: "/dashboard/overview" },
  { icon: <User className="w-5 h-5" />, label: "Account", to: "/account" },
  { icon: <CreditCard className="w-5 h-5" />, label: "Pricing", to: "/dashboard/pricing" },
  { icon: <Settings className="w-5 h-5" />, label: "Settings", to: "/dashboard/settings" },
  { icon: <DollarSign className="w-5 h-5" />, label: "Refer & Earn", to: "/dashboard/refer" },
  { icon: <FileText className="w-5 h-5" />, label: "Documentation", to: "/dashboard/docs" },
];

export const SidebarItemList = () => {
  const location = useLocation();

  return (
    <ul className="space-y-2">
      {sidebarItems.map((item, index) => {
        const isActive = location.pathname === item.to;

        return (
          <li key={index}>
            <Link
              to={item.to}
              className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-colors duration-200 hover:bg-muted ${
                isActive ? "bg-muted font-semibold text-primary" : "text-muted-foreground"
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
};
