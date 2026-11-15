# 把 Unity 导出的工程接进 Flutter 的 iOS 工程（只需要跑一次，重复跑不会重复添加）：
#   1. 工作区里加上 ios/unityLibrary/Unity-iPhone.xcodeproj
#   2. Runner 链接并内嵌 UnityFramework.framework（Embed & Sign）
#   3. 把 Flutter 的「Thin Binary」步骤挪到「Embed Frameworks」后面，避免循环依赖
# 这就是 flutter_embed_unity 文档里要在 Xcode 里手点的那几步。
# 用法：GEM_HOME=<cocoapods 的 gems 目录> ruby tools/unity/link_unity.rb ios
require 'xcodeproj'

ios = File.expand_path(ARGV[0] || 'ios')

ws_file = File.join(ios, 'Runner.xcworkspace', 'contents.xcworkspacedata')
xml = File.read(ws_file)
unless xml.include?('Unity-iPhone.xcodeproj')
  xml.sub!('</Workspace>', "   <FileRef\n      location = \"group:unityLibrary/Unity-iPhone.xcodeproj\">\n   </FileRef>\n</Workspace>")
  File.write(ws_file, xml)
  puts '工作区：已加入 Unity-iPhone.xcodeproj'
end

proj = Xcodeproj::Project.open(File.join(ios, 'Runner.xcodeproj'))
target = proj.targets.find { |t| t.name == 'Runner' }
group = proj.frameworks_group
ref = group.files.find { |f| f.path == 'UnityFramework.framework' }
unless ref
  ref = group.new_file('UnityFramework.framework')
  ref.source_tree = 'BUILT_PRODUCTS_DIR'
  ref.explicit_file_type = 'wrapper.framework'
  ref.last_known_file_type = nil
  ref.include_in_index = '0'
end

link = target.frameworks_build_phase
link.add_file_reference(ref, true) unless link.files_references.include?(ref)

embed = target.copy_files_build_phases.find { |p| p.symbol_dst_subfolder_spec == :frameworks }
unless embed
  embed = target.new_copy_files_build_phase('Embed Frameworks')
  embed.symbol_dst_subfolder_spec = :frameworks
end
unless embed.files_references.include?(ref)
  bf = embed.add_file_reference(ref, true)
  bf.settings = { 'ATTRIBUTES' => %w[CodeSignOnCopy RemoveHeadersOnCopy] }
end

thin = target.build_phases.find { |p| p.respond_to?(:name) && p.name == 'Thin Binary' }
if thin && target.build_phases.index(thin) < target.build_phases.index(embed)
  target.build_phases.delete(thin)
  target.build_phases.insert(target.build_phases.index(embed) + 1, thin)
end

proj.save
puts "Runner：UnityFramework 已链接并内嵌。构建步骤顺序：#{target.build_phases.map { |p| p.respond_to?(:name) && p.name ? p.name : p.class.name.split('::').last }.join(' → ')}"
